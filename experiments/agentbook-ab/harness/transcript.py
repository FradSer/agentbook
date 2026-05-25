"""Turn-by-turn records for one agentic episode."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Turn:
    turn: int
    command: str
    stdout_tail: str
    stderr_tail: str
    returncode: int
    latency_ms: int


@dataclass
class Episode:
    turns: list[Turn] = field(default_factory=list)
    stop_reason: str = "budget"  # done | budget | parse_failures | llm_error
    turns_used: int = 0
    error: str | None = None
    notes: list[str] = field(default_factory=list)  # raw replies on parse failures

    def to_dict(self) -> dict:
        return {
            "stop_reason": self.stop_reason,
            "turns_used": self.turns_used,
            "error": self.error,
            "notes": self.notes,
            "turns": [asdict(t) for t in self.turns],
        }
