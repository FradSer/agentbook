"""Google AI Studio (Gemini API) chat client via the google-genai SDK.

Same chat() interface as OpenRouterLLM/OllamaLLM so the agentic loop stays
provider-agnostic. Maps OpenAI-style roles (system/user/assistant) onto Gemini's
shape (system_instruction + user/model turns), token-bucket rate-limits to respect
AI Studio quotas, and retries transient 429/503 plus connection drops.

Uses STREAMING generation: gemma-4 is a reasoning model that can spend minutes on
an agentic prompt (observed 170s / ~22k chars). A non-streaming call leaves the
socket idle that whole window and the server drops it (RemoteProtocolError
"Server disconnected"); streaming keeps bytes flowing so the connection survives.

The SDK is imported lazily so the dependency is only required when this provider
is actually selected.
"""

from __future__ import annotations

import os
import threading
import time

from harness.llm_openrouter import BudgetExhausted, LLMError

_TRANSIENT = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "INTERNAL")
_CONN_DROP = (
    "disconnect",
    "timeout",
    "timed out",
    "connection",
    "remoteprotocol",
    "incomplete",
    "eof",
)


class GeminiLLM:
    def __init__(
        self,
        *,
        rpm: int = 30,
        day_cap: int = 14000,
        max_tokens: int = 8000,
        api_key_env: str = "GEMINI_API_KEY",
        timeout: float = 600.0,
    ) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise LLMError("google-genai not installed (uv add google-genai)") from exc
        key = os.environ.get(api_key_env)
        if not key:
            raise LLMError(f"{api_key_env} not set")
        self._types = types
        self._client = genai.Client(api_key=key)
        self.max_tokens = max_tokens
        self.day_count = 0
        self.day_cap = day_cap
        self._rpm = max(rpm, 1)
        self._tokens = float(self._rpm)
        self._last = time.monotonic()
        self._lock = threading.Lock()
        self._timeout = timeout

    def close(self) -> None:
        pass

    def _acquire(self) -> None:
        """Token-bucket: block until a request slot frees, enforce the day cap."""
        with self._lock:
            if self.day_count >= self.day_cap:
                raise BudgetExhausted(f"gemini day cap {self.day_cap} reached")
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self._rpm, self._tokens + (now - self._last) * self._rpm / 60.0
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self.day_count += 1
                    return
                time.sleep((1.0 - self._tokens) * 60.0 / self._rpm)

    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        seed: int = 0,
    ) -> str:
        types = self._types
        system_instruction: str | None = None
        contents = []
        for m in messages:
            text = m.get("content") or ""
            if m["role"] == "system":
                system_instruction = (
                    f"{system_instruction}\n\n{text}" if system_instruction else text
                )
                continue
            grole = "model" if m["role"] == "assistant" else "user"
            contents.append(
                types.Content(role=grole, parts=[types.Part.from_text(text=text)])
            )

        cfg: dict = {
            "temperature": temperature,
            "max_output_tokens": self.max_tokens,
            "seed": seed,
        }
        if system_instruction:
            cfg["system_instruction"] = system_instruction
        config = types.GenerateContentConfig(
            http_options=types.HttpOptions(timeout=int(self._timeout * 1000)), **cfg
        )

        last_exc: Exception | None = None
        for attempt in range(6):
            self._acquire()
            try:
                pieces: list[str] = []
                for chunk in self._client.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ):
                    if chunk.text:
                        pieces.append(chunk.text)
                return "".join(pieces)
            except Exception as exc:  # noqa: BLE001 - classify transient vs fatal
                msg = str(exc)
                transient = any(code in msg for code in _TRANSIENT) or any(
                    s in msg.lower() for s in _CONN_DROP
                )
                if transient:
                    last_exc = exc
                    # Jittered backoff so concurrent workers desynchronize on
                    # retry instead of re-colliding (jitter from day_count, not
                    # Math.random, to keep runs reproducible).
                    base = min(60.0, (2**attempt) * 3.0)
                    jitter = (self.day_count % 7) * 0.5
                    time.sleep(base + jitter)
                    continue
                raise LLMError(f"gemini transport: {msg[:200]}") from exc
        raise LLMError(f"gemini: retries exhausted: {str(last_exc)[:200]}")
