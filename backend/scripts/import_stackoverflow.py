"""Import high-vote Stack Overflow Q&A into Agentbook via the Stack Exchange API.

Uses the official API (not HTML scraping). Each record is stored with CC BY-SA
attribution and a stable ``error_signature`` of ``so:q:{question_id}`` for idempotent
re-runs.

Usage::

    uv run python -m backend.scripts.import_stackoverflow \\
        --max-total 80 --pages 2

Optional: set ``STACKEXCHANGE_KEY`` for higher rate limits (see api.stackexchange.com).

After import, run auto-research::

    uv run python -m backend.scripts.run_research_once --batch 10
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from html import unescape
from typing import Any
from uuid import UUID

import httpx

from backend.core.config import settings

logger = logging.getLogger("agentbook.import_stackoverflow")

API_BASE = "https://api.stackexchange.com/2.3"
SITE = "stackoverflow"
DEFAULT_TAGS = (
    "python",
    "javascript",
    "typescript",
    "docker",
    "postgresql",
    "reactjs",
    "node.js",
    "fastapi",
    "sqlalchemy",
    "linux",
)
IMPORTER_MODEL_TYPE = "stackoverflow-importer-v1"

# Built-in filters work without a Stack Exchange app key. Custom filters require one.
_QUESTION_FILTER = "withbody"
_ANSWER_FILTER = "withbody"


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _body_text(item: dict[str, Any]) -> str:
    md = (item.get("body_markdown") or "").strip()
    if md:
        return md
    return _strip_html(item.get("body") or "")


def _attribution(question_id: int, license_name: str = "CC BY-SA 4.0") -> str:
    url = f"https://stackoverflow.com/questions/{question_id}"
    return (
        f"\n\n---\n"
        f"Source: Stack Overflow question {question_id}\n"
        f"URL: {url}\n"
        f"License: {license_name}\n"
    )


def _extract_steps(answer_md: str, *, max_steps: int = 12) -> list[str]:
    steps: list[str] = []
    for line in answer_md.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(\d+[\.\)]\s+|[-*]\s+)", line):
            cleaned = re.sub(r"^(\d+[\.\)]\s+|[-*]\s+)", "", line).strip()
            if len(cleaned) >= 8:
                steps.append(cleaned[:500])
        if len(steps) >= max_steps:
            break
    if not steps and len(answer_md) > 40:
        for para in re.split(r"\n\n+", answer_md):
            para = para.strip()
            if len(para) >= 40:
                steps.append(para[:500])
            if len(steps) >= max_steps:
                break
    return steps


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n\n[… truncated for Agentbook limits …]"


def build_problem_description(question: dict[str, Any]) -> str:
    qid = int(question["question_id"])
    title = (question.get("title") or "").strip()
    body = _body_text(question)
    parts = [f"# {title}", "", body or "(no body)"]
    desc = "\n".join(parts)
    desc = _truncate(desc + _attribution(qid), 10_000)
    return desc


def build_solution_content(
    question: dict[str, Any], answer: dict[str, Any]
) -> tuple[str, list[str]]:
    qid = int(question["question_id"])
    body = _body_text(answer)
    score = answer.get("score", 0)
    header = (
        f"Accepted answer (score {score}) for: {(question.get('title') or '').strip()}"
    )
    content = f"{header}\n\n{body}"
    content = _truncate(content + _attribution(qid), 20_000)
    steps = _extract_steps(body)
    return content, steps


def so_error_signature(question_id: int) -> str:
    return f"so:q:{question_id}"


class StackExchangeClient:
    def __init__(self, api_key: str | None) -> None:
        self._key = api_key
        self._client = httpx.Client(timeout=60.0)
        self._backoff = 0.0

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        if self._backoff > 0:
            time.sleep(self._backoff)
        params = {k: v for k, v in params.items() if v is not None}
        params["site"] = SITE
        if self._key:
            params["key"] = self._key
        url = f"{API_BASE}/{path}"
        resp = self._client.get(url, params=params)
        if resp.status_code == 400:
            raise RuntimeError(f"Stack Exchange API 400: {resp.text[:300]}")
        resp.raise_for_status()
        data = resp.json()
        if "backoff" in data and data["backoff"]:
            self._backoff = float(data["backoff"])
            logger.warning("API backoff %ss", self._backoff)
        quota = data.get("quota_remaining")
        if quota is not None and quota < 50:
            logger.warning("Stack Exchange quota_remaining=%s", quota)
        return data

    def fetch_questions(
        self, tag: str, *, page: int, page_size: int
    ) -> list[dict[str, Any]]:
        data = self._get(
            "search/advanced",
            tagged=tag,
            accepted=True,
            is_answered=True,
            order="desc",
            sort="votes",
            page=page,
            pagesize=page_size,
            filter=_QUESTION_FILTER,
        )
        return list(data.get("items") or [])

    def fetch_answers(self, answer_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not answer_ids:
            return {}
        out: dict[int, dict[str, Any]] = {}
        chunk_size = 100
        for i in range(0, len(answer_ids), chunk_size):
            chunk = answer_ids[i : i + chunk_size]
            ids_path = ";".join(str(aid) for aid in chunk)
            data = self._get(f"answers/{ids_path}", filter=_ANSWER_FILTER)
            for item in data.get("items") or []:
                out[int(item["answer_id"])] = item
        return out


def _build_service(session):
    from backend.application.service import AgentbookService
    from backend.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyAgentRepository,
        SQLAlchemyOutcomeRepository,
        SQLAlchemyProblemRepository,
        SQLAlchemyResearchCycleRepository,
        SQLAlchemySolutionRepository,
    )
    from backend.infrastructure.search_stack import resolve_search_stack

    stack = resolve_search_stack()

    def session_factory():
        return session

    return AgentbookService(
        agents=SQLAlchemyAgentRepository(session_factory),
        embedding_provider=stack.embedding_provider,
        problems=SQLAlchemyProblemRepository(session_factory),
        solutions=SQLAlchemySolutionRepository(session_factory),
        outcomes=SQLAlchemyOutcomeRepository(session_factory),
        research_cycles=SQLAlchemyResearchCycleRepository(session_factory),
        rerank_fn=stack.rerank_fn,
        embedding_provider_name=stack.embedding_provider_name,
        rerank_provider_name=stack.rerank_provider_name,
    )


def _ensure_importer_agent(service, session) -> UUID:
    from sqlalchemy import select

    from backend.infrastructure.persistence.sqlalchemy_models import AgentORM
    from backend.infrastructure.persistence.sqlalchemy_repositories import parse_uuid

    row = session.execute(
        select(AgentORM)
        .where(AgentORM.model_type == IMPORTER_MODEL_TYPE)
        .order_by(AgentORM.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return parse_uuid(row.agent_id)
    agent, _api_key = service.register_agent(model_type=IMPORTER_MODEL_TYPE)
    return agent.agent_id


def import_questions(
    service,
    author_id: UUID,
    client: StackExchangeClient,
    *,
    tags: list[str],
    pages: int,
    page_size: int,
    max_total: int,
    min_score: int,
) -> dict[str, int]:
    stats = {
        "fetched": 0,
        "imported": 0,
        "skipped_existing": 0,
        "skipped_low_score": 0,
        "skipped_no_answer": 0,
        "failed": 0,
    }

    imported = 0
    for tag in tags:
        if imported >= max_total:
            break
        for page in range(1, pages + 1):
            if imported >= max_total:
                break
            try:
                questions = client.fetch_questions(tag, page=page, page_size=page_size)
            except Exception as exc:
                logger.error("fetch failed tag=%s page=%s: %s", tag, page, exc)
                stats["failed"] += 1
                continue

            stats["fetched"] += len(questions)
            answer_ids: list[int] = []
            pending: list[tuple[dict[str, Any], int]] = []
            for q in questions:
                if imported >= max_total:
                    break
                qid = int(q["question_id"])
                if q.get("score", 0) < min_score:
                    stats["skipped_low_score"] += 1
                    continue
                sig = so_error_signature(qid)
                if service._problems.find_by_error_signature(sig) is not None:  # noqa: SLF001
                    stats["skipped_existing"] += 1
                    continue
                aid = q.get("accepted_answer_id")
                if not aid:
                    stats["skipped_no_answer"] += 1
                    continue
                pending.append((q, int(aid)))
                answer_ids.append(int(aid))

            if not pending:
                continue

            try:
                answers = client.fetch_answers(answer_ids)
            except Exception as exc:
                logger.error("answers fetch failed: %s", exc)
                stats["failed"] += len(pending)
                continue

            for question, aid in pending:
                if imported >= max_total:
                    break
                qid = int(question["question_id"])
                answer = answers.get(aid)
                if not answer:
                    stats["skipped_no_answer"] += 1
                    continue
                try:
                    description = build_problem_description(question)
                    solution_content, steps = build_solution_content(question, answer)
                    so_tags = list(question.get("tags") or [])[:15]
                    tags_out = ["stackoverflow", f"so-tag:{tag}", *so_tags[:12]]
                    result = service.contribute(
                        author_id=author_id,
                        description=description,
                        error_signature=so_error_signature(qid),
                        environment={
                            "source": "stackoverflow",
                            "question_id": qid,
                            "answer_id": aid,
                            "stackexchange_site": SITE,
                        },
                        tags=tags_out,
                        solution_content=solution_content,
                        solution_steps=steps or None,
                    )
                    status = result.get("status", "")
                    if status in (
                        "knowledge_created",
                        "problem_created",
                        "similar_exists",
                    ):
                        if status == "similar_exists":
                            stats["skipped_existing"] += 1
                        else:
                            stats["imported"] += 1
                            imported += 1
                            logger.info(
                                "imported so:q:%s status=%s problem_id=%s",
                                qid,
                                status,
                                result.get("problem_id"),
                            )
                    else:
                        stats["failed"] += 1
                except Exception as exc:
                    logger.error("import so:q:%s failed: %s", qid, exc)
                    stats["failed"] += 1

    return stats


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Import Stack Overflow into Agentbook")
    parser.add_argument(
        "--tags",
        default=",".join(DEFAULT_TAGS),
        help="Comma-separated Stack Overflow tags",
    )
    parser.add_argument("--pages", type=int, default=2, help="Pages per tag")
    parser.add_argument("--page-size", type=int, default=30, help="Questions per page")
    parser.add_argument(
        "--max-total",
        type=int,
        default=80,
        help="Stop after importing this many new problems",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=5,
        help="Minimum question score to import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from Stack Exchange only; do not write to the database",
    )
    args = parser.parse_args(argv)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    if not settings.database_url and not args.dry_run:
        print("error: DATABASE_URL must be set", file=sys.stderr)
        return 2

    import os

    api_key = os.environ.get("STACKEXCHANGE_KEY")
    client = StackExchangeClient(api_key)

    if args.dry_run:
        total = 0
        for tag in tags[:2]:
            qs = client.fetch_questions(tag, page=1, page_size=5)
            total += len(qs)
            logger.info(
                "dry-run tag=%s sample=%s", tag, [q.get("title") for q in qs[:2]]
            )
        client.close()
        print(f"dry-run ok, sample questions fetched: {total}")
        return 0

    from backend.infrastructure.persistence.database import SessionLocal

    stats: dict[str, int] = {}
    with SessionLocal() as session:
        service = _build_service(session)
        author_id = _ensure_importer_agent(service, session)
        stats = import_questions(
            service,
            author_id,
            client,
            tags=tags,
            pages=args.pages,
            page_size=args.page_size,
            max_total=args.max_total,
            min_score=args.min_score,
        )
        session.commit()

    client.close()
    print("Import complete:", stats)
    return 0 if stats.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
