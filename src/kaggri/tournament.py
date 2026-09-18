"""Run agent-vs-agent panels, reproducing the methodology already in use.

Requires the game engine, which is **not on PyPI** — it lives only on
kaggle-environments master and needs Python >= 3.11:

    pip install --no-deps git+https://github.com/Kaggle/kaggle-environments.git

The three rules this module enforces, all of which the existing evidence file
already follows and all of which are easy to get wrong:

1. **Both seats.** Seat 0 and seat 1 are not symmetric — market orders resolve
   in seat order. Playing one seat measures half the game.
2. **Shared seeds.** The same seed must be used for both seats and every
   candidate, so margins are paired and differences are attributable to the
   agent rather than to the world.
3. **Held-back seeds.** Screen on development seeds, then confirm on seeds that
   were never used during selection. Reusing screening seeds turns model
   selection into overfitting you cannot see.
"""
from __future__ import annotations

import itertools
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

ENV_NAME = "kaggriculture"
DEFAULT_STEPS = 720


class EngineUnavailable(RuntimeError):
    """Raised with the actual remedy rather than a bare ImportError."""


def require_engine():
    """Import the engine, or explain precisely how to get it."""
    import sys
    try:
        from kaggle_environments import make  # noqa: F401
    except ImportError as e:
        raise EngineUnavailable(
            f"kaggle_environments is not importable (running Python "
            f"{sys.version_info.major}.{sys.version_info.minor}).\n"
            "The kaggriculture env is NOT in the PyPI release — install from master:\n"
            "  pip install --no-deps git+https://github.com/Kaggle/kaggle-environments.git\n"
            "which needs Python >= 3.11."
        ) from e
    import kaggle_environments as ke
    envs = (Path(ke.__file__).parent / "envs")
    if not (envs / ENV_NAME).exists():
        raise EngineUnavailable(
            f"kaggle_environments {getattr(ke, 'version', '?')} has no '{ENV_NAME}' env.\n"
            "The PyPI release does not bundle it; install from GitHub master instead:\n"
            "  pip install --no-deps git+https://github.com/Kaggle/kaggle-environments.git")
    from kaggle_environments import make
    return make


@dataclass
class GameResult:
    candidate: str
    opponent: str
    seed: int
    seat: int                 # which seat the candidate played
    rewards: list             # as returned by the engine, in seat order
    margin: float             # candidate reward - opponent reward
    statuses: list
    seconds: float

    @property
    def outcome(self) -> str:
        return "win" if self.margin > 0 else ("loss" if self.margin < 0 else "tie")


def play(candidate: str | Path, opponent: str | Path, seed: int, seat: int,
         steps: int = DEFAULT_STEPS, debug: bool = False) -> GameResult:
    """One game. `seat` is the candidate's index; agents are swapped accordingly."""
    make = require_engine()
    agents = [str(candidate), str(opponent)] if seat == 0 else [str(opponent), str(candidate)]
    env = make(ENV_NAME, configuration={"episodeSteps": steps}, debug=debug)
    t0 = time.time()
    env.run(agents)
    final = env.steps[-1]
    rewards = [s.get("reward") for s in final]
    statuses = [s.get("status") for s in final]
    mine, theirs = (rewards[0], rewards[1]) if seat == 0 else (rewards[1], rewards[0])
    return GameResult(
        candidate=Path(candidate).parent.name if Path(candidate).name == "main.py" else str(candidate),
        opponent=Path(opponent).parent.name if Path(opponent).name == "main.py" else str(opponent),
        seed=seed, seat=seat, rewards=rewards,
        margin=float((mine or 0) - (theirs or 0)),
        statuses=statuses, seconds=time.time() - t0)


def panel(candidates: dict[str, str | Path], opponents: dict[str, str | Path],
          seeds: Sequence[int], seats: Iterable[int] = (0, 1),
          steps: int = DEFAULT_STEPS, out: Path | None = None,
          progress: bool = True) -> list[GameResult]:
    """Every candidate against every opponent, on every seed, in both seats.

    Results stream to `out` as JSONL as they finish — a panel is hours of
    compute and losing it to a crash at game 130 is avoidable.
    """
    combos = list(itertools.product(candidates.items(), opponents.items(), seeds, seats))
    print(f"{len(combos)} games: {len(candidates)} candidates x {len(opponents)} opponents "
          f"x {len(seeds)} seeds x {len(list(seats))} seats")
    results: list[GameResult] = []
    fh = open(out, "a") if out else None
    try:
        for i, ((cname, cpath), (oname, opath), seed, seat) in enumerate(combos, 1):
            r = play(cpath, opath, seed, seat, steps)
            r.candidate, r.opponent = cname, oname
            results.append(r)
            if fh:
                fh.write(json.dumps(asdict(r)) + "\n"); fh.flush()
            if progress:
                print(f"  [{i}/{len(combos)}] {cname} vs {oname} seed={seed} seat={seat} "
                      f"-> {r.outcome} {r.margin:+.0f} ({r.seconds:.0f}s)", flush=True)
    finally:
        if fh:
            fh.close()
    return results


def load_results(path: Path) -> list[GameResult]:
    return [GameResult(**json.loads(l)) for l in Path(path).read_text().splitlines() if l.strip()]
