"""Local Ollama chat client (OpenAI-compatible endpoint).

Same chat() interface as OpenRouterLLM so the agentic loop is provider-agnostic.
No rate limiter or day budget -- local inference has no per-minute/day caps. A
generous timeout covers slow on-device generation.
"""

from __future__ import annotations

import json

import httpx

from harness.llm_openrouter import LLMError

DEFAULT_BASE = "http://localhost:11434/v1"


def _recover_toolcall_500(body_text: str) -> str | None:
    """Recover the model's real output from Ollama's gpt-oss harmony bug.

    Ollama (all 0.11-0.24) mis-parses gpt-oss's harmony output as a tool call and
    returns HTTP 500 `error parsing tool call: raw='<the model output>' err=...`
    (ollama/ollama #11800/#11781/#12064/#12203). The model DID produce a usable
    answer -- it's in `raw=`. We extract it so a runtime bug doesn't waste the
    episode. Returns the recovered text (with its ```bash / ```diff block) or None.
    """
    try:
        msg = json.loads(body_text).get("error", "")
        if isinstance(msg, dict):
            msg = msg.get("message", "")
    except (ValueError, AttributeError):
        msg = body_text
    if "raw=" not in msg:
        return None
    raw = msg.split("raw=", 1)[1].lstrip()
    if raw[:1] in "'\"":
        quote = raw[0]
        raw = raw[1:]
        # Go appends ` err=...` after the quoted raw; cut there, else trailing quote
        delim = f"{quote} err="
        raw = raw.rsplit(delim, 1)[0] if delim in raw else raw.rstrip(quote)
    # un-double-escape if Go escaped the newlines/tabs into literal backslashes
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return raw.strip() or None


class OllamaLLM:
    def __init__(
        self,
        *,
        base: str = DEFAULT_BASE,
        max_tokens: int = 8000,
        reasoning_effort: str = "low",
        timeout: float = 1800.0,
    ) -> None:
        self.base = base.rstrip("/")
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
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
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        # gpt-oss is a reasoning model; reasoning_effort is its capability knob.
        # "high" = max reasoning quality (needs large max_tokens so the bash
        # block is still emitted after the chain-of-thought).
        if "gpt-oss" in model:
            body["reasoning_effort"] = self.reasoning_effort
        try:
            r = self._client.post(f"{self.base}/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"ollama transport: {exc}") from exc
        if r.status_code == 500 and "tool call" in r.text:
            recovered = _recover_toolcall_500(r.text)
            if recovered:
                return recovered
        if r.status_code != 200:
            raise LLMError(f"ollama http {r.status_code}: {r.text[:200]}")
        data = r.json()
        if "error" in data:
            raise LLMError(f"ollama error: {str(data['error'])[:200]}")
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning") or ""
        # gpt-oss on ollama sometimes emits the FINAL answer's code fence only in
        # the reasoning channel (high reasoning_effort + long context can leave
        # `content` empty or fence-less while the intended ```bash/```diff/```edit
        # block sits at the tail of `reasoning`). Returning a fence-less reasoning
        # blob makes the agent loop see "no block" and burn parse-failure strikes.
        # Prefer whichever channel actually carries an actionable fence.
        if "```" in content:
            return content
        if "```" in reasoning:
            return reasoning
        return content or reasoning
