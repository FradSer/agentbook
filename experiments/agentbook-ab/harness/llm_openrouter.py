"""OpenRouter chat client for the weak-model panel.

Handles the binding free-tier constraints: a process-wide sliding-window rate
limiter (default 20 req/min), a persistent per-day budget guard, exponential
backoff on 429/5xx, and optional free-first -> same-model paid fallback so a run
can finish without changing model identity.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RUNS_V2 = ROOT / "runs_v2"
BUDGET_FILE = RUNS_V2 / "_budget.json"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    pass


class BudgetExhausted(RuntimeError):
    pass


def load_openrouter_key() -> str:
    import os

    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env = ROOT.parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise LLMError("OPENROUTER_API_KEY not found in env or root .env")


class RateLimiter:
    """Process-wide sliding-window limiter (thread-safe)."""

    def __init__(self, rpm: int) -> None:
        self.rpm = rpm
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            while self._calls and now - self._calls[0] > 60:
                self._calls.popleft()
            if len(self._calls) >= self.rpm:
                sleep_for = 60 - (now - self._calls[0]) + 0.05
                time.sleep(max(sleep_for, 0))
                now = time.time()
                while self._calls and now - self._calls[0] > 60:
                    self._calls.popleft()
            self._calls.append(time.time())


class DayBudget:
    """Persistent per-day request counter (resets at date rollover)."""

    def __init__(self, cap: int, path: Path = BUDGET_FILE) -> None:
        self.cap = cap
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"date": str(date.today()), "count": 0}

    def charge(self) -> None:
        with self._lock:
            state = self._read()
            today = str(date.today())
            if state.get("date") != today:
                state = {"date": today, "count": 0}
            if state["count"] >= self.cap:
                raise BudgetExhausted(
                    f"day budget {self.cap} exhausted ({state['count']} used)"
                )
            state["count"] += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state) + "\n")

    def remaining(self) -> int:
        state = self._read()
        if state.get("date") != str(date.today()):
            return self.cap
        return max(self.cap - state["count"], 0)


class OpenRouterLLM:
    def __init__(
        self,
        *,
        rpm: int = 20,
        day_cap: int = 200,
        max_retries: int = 4,
        backoff_base: float = 6.0,
        max_tokens: int = 4096,
        allow_paid_fallback: bool = False,
        timeout: float = 180.0,
    ) -> None:
        self.key = load_openrouter_key()
        self.limiter = RateLimiter(rpm)
        self.budget = DayBudget(day_cap)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_tokens = max_tokens
        self.allow_paid_fallback = allow_paid_fallback
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _post(self, model: str, messages: list[dict], temperature: float, seed: int):
        # NOTE: `seed` is intentionally NOT sent. Most free/open providers ignore
        # it, and some (gpt-oss on the JAX/OpenInference backend) hard-error
        # ("JAX does not support per-request seed", 502). The intended seed is
        # still recorded in each cell's provenance for audit.
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        # gpt-oss is a reasoning model: with a long agentic prompt it spends the
        # token budget on reasoning and never emits the bash block (content stays
        # empty). Cap reasoning effort low so the actual command is produced.
        if "gpt-oss" in model:
            body["reasoning"] = {"effort": "low"}
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/agentbook/eval",
            "X-Title": "agentbook-ab",
        }
        return self._client.post(API_URL, json=body, headers=headers)

    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        seed: int = 0,
    ) -> str:
        """One completion. Raises LLMError after retries, BudgetExhausted on cap."""
        tried_paid = False
        active_model = model
        for attempt in range(self.max_retries):
            self.budget.charge()
            self.limiter.acquire()
            try:
                r = self._post(active_model, messages, temperature, seed)
            except httpx.HTTPError as exc:
                self._sleep(attempt)
                last_err = f"transport: {exc}"
                continue
            if r.status_code == 200:
                data = r.json()
                if "error" in data:
                    last_err = f"api error: {str(data['error'])[:200]}"
                    self._sleep(attempt)
                    continue
                choice = (data.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                content = msg.get("content") or msg.get("reasoning") or ""
                if content.strip():
                    return content
                last_err = "empty completion"
                self._sleep(attempt)
                continue
            last_err = f"http {r.status_code}: {r.text[:150]}"
            # free -> same-model paid fallback on any free-tier unavailability:
            # 429 (upstream rate-limit), 400 (e.g. expired upstream provider key),
            # 402 (free credits required), 404 (free variant pulled).
            if (
                self.allow_paid_fallback
                and not tried_paid
                and active_model.endswith(":free")
                and r.status_code in (400, 402, 404, 429)
            ):
                active_model = active_model[: -len(":free")]
                tried_paid = True
                continue
            if r.status_code in (408, 429, 500, 502, 503):
                self._sleep(attempt)
                continue
            raise LLMError(f"http {r.status_code}: {r.text[:200]}")
        raise LLMError(f"exhausted retries for {model}: {last_err}")

    def _sleep(self, attempt: int) -> None:
        time.sleep(self.backoff_base * (attempt + 1))
