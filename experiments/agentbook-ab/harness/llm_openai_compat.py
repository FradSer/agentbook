"""Generic OpenAI-compatible chat client (internal gateway / vLLM / etc.).

Same chat() interface as OpenRouterLLM/OllamaLLM so the agentic loop stays
provider-agnostic. Points at any base_url exposing POST {base}/chat/completions.
No day budget (internal endpoints are unmetered); a token-bucket rate limiter and
backoff on 429/5xx/transport drops keep it polite under concurrency.

Reasoning models (e.g. qwen3.6) return their chain-of-thought in a separate
`reasoning_content` field and the final answer in `content`; we read `content`
first and fall back to `reasoning_content` only when content is empty.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque

import httpx

from harness.llm_openrouter import LLMError


class _RateLimiter:
    def __init__(self, rpm: int) -> None:
        self.rpm = max(rpm, 1)
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


class OpenAICompatLLM:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        rpm: int = 60,
        max_tokens: int = 8000,
        max_retries: int = 5,
        backoff_base: float = 4.0,
        timeout: float = 600.0,
    ) -> None:
        base = base_url or os.environ.get(
            "OPENAI_COMPAT_BASE", "http://10.10.0.195:8317/v1"
        )
        self.base = base.rstrip("/")
        self.key = api_key or os.environ.get("OPENAI_COMPAT_KEY", "sk-dummy")
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.limiter = _RateLimiter(rpm)
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        seed: int = 0,
    ) -> str:
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        last_err = ""
        for attempt in range(self.max_retries):
            self.limiter.acquire()
            try:
                r = self._client.post(
                    f"{self.base}/chat/completions", json=body, headers=headers
                )
            except httpx.HTTPError as exc:
                last_err = f"transport: {exc}"
                time.sleep(self.backoff_base * (attempt + 1))
                continue
            if r.status_code == 200:
                data = r.json()
                if "error" in data:
                    last_err = f"api error: {str(data['error'])[:200]}"
                    time.sleep(self.backoff_base * (attempt + 1))
                    continue
                msg = (data.get("choices") or [{}])[0].get("message") or {}
                content = (
                    msg.get("content")
                    or msg.get("reasoning_content")
                    or msg.get("reasoning")
                    or ""
                )
                if content.strip():
                    return content
                last_err = "empty completion"
                time.sleep(self.backoff_base * (attempt + 1))
                continue
            last_err = f"http {r.status_code}: {r.text[:150]}"
            if r.status_code in (408, 429, 500, 502, 503, 504):
                time.sleep(self.backoff_base * (attempt + 1))
                continue
            raise LLMError(f"http {r.status_code}: {r.text[:200]}")
        raise LLMError(f"exhausted retries for {model}: {last_err}")
