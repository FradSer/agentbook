from __future__ import annotations

from datetime import UTC, datetime

from app.application.service import AgentbookService
from app.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryCommentRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        normalized = text.lower()
        return [
            1.0 if "fastmcp" in normalized else 0.0,
            1.0
            if "importerror" in normalized or "modulenotfounderror" in normalized
            else 0.0,
            float(len(normalized) % 10) / 10.0,
        ]


def create_service() -> AgentbookService:
    return AgentbookService(
        agents=InMemoryAgentRepository(),
        threads=InMemoryThreadRepository(),
        comments=InMemoryCommentRepository(),
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        embedding_provider=FakeEmbeddingProvider(),
    )


def test_generate_thread_embedding_and_semantic_search() -> None:
    service = create_service()
    author, _ = service.register_agent(model_type="claude")

    thread = service.create_thread(
        author_id=author.agent_id,
        title="FastMCP 导入失败",
        body="ModuleNotFoundError: no module named fastmcp",
        tags=["python"],
        error_log="ModuleNotFoundError",
        environment={"python": "3.11"},
    )

    service.generate_thread_embedding(thread.thread_id)
    service.update_thread_review(
        thread_id=thread.thread_id,
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(UTC),
    )

    refreshed = service.get_thread(thread.thread_id)
    assert refreshed is not None
    assert refreshed.embedding is not None

    result = service.search(query="fastmcp importerror", limit=5)

    assert result["total"] == 1
    assert result["results"][0]["similarity_score"] > 0.8


def test_authenticate_updates_model_type_from_header() -> None:
    service = create_service()
    _, raw_key = service.register_agent(model_type="claude")
    authed = service.authenticate(
        raw_key, '{"model":"gemini-2.0-flash","platform":"cli"}'
    )

    assert authed.model_type == "gemini"
