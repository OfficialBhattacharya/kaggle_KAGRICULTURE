"""The agent registry — what exists, what it scored, where it came from.

Kept as data rather than prose so packaging, verification and the worklog all
read the same record. `agents/<name>/agent.json` is the unit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO / "agents"


@dataclass
class Agent:
    name: str
    title: str
    source_sha256: str
    submitted_utc: str | None = None
    leaderboard_score: float | None = None
    kernel_ref: str | None = None
    derived_from: list[dict] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    evidence: str | None = None
    notes: str = ""

    @property
    def dir(self) -> Path:
        return AGENTS_DIR / self.name

    @property
    def main_py(self) -> Path:
        return self.dir / "main.py"

    def exists(self) -> bool:
        return self.main_py.exists()


def load_all() -> list[Agent]:
    out = []
    for meta in sorted(AGENTS_DIR.glob("*/agent.json")):
        out.append(Agent(**json.loads(meta.read_text())))
    return sorted(out, key=lambda a: -(a.leaderboard_score or 0))


def best() -> Agent:
    agents = [a for a in load_all() if a.leaderboard_score is not None]
    if not agents:
        raise LookupError("no agent has a recorded leaderboard score")
    return agents[0]
