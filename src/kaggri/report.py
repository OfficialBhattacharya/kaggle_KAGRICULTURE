"""Summarise a panel the way the existing evidence file does.

Two numbers matter and they answer different questions:

- **match points** (win=1, tie=0.5) is what the ladder actually rewards — the
  competition states the coin difference does not affect rating, only W/L/T.
- **cash margin** is far lower-variance and detects a real improvement with
  many fewer games, but a big margin against a weak opponent is not rating.

Report both, and always per-opponent: a pooled mean is dominated by whichever
opponent is easiest, which is how a change that only beats weak bots looks good.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

import random


@dataclass
class Summary:
    games: int
    wins: int
    losses: int
    ties: int
    points: float
    mean_margin: float
    worst_margin: float

    def __str__(self) -> str:
        return (f"{self.wins}W/{self.losses}L/{self.ties}T over {self.games} games  "
                f"points={self.points:.3f}  mean margin={self.mean_margin:+.0f}  "
                f"worst={self.worst_margin:+.0f}")


def summarise(results: Sequence) -> Summary:
    if not results:
        return Summary(0, 0, 0, 0, 0.0, 0.0, 0.0)
    w = sum(r.margin > 0 for r in results)
    l = sum(r.margin < 0 for r in results)
    t = sum(r.margin == 0 for r in results)
    margins = [r.margin for r in results]
    return Summary(len(results), w, l, t, (w + 0.5 * t) / len(results),
                   statistics.fmean(margins), min(margins))


def by_opponent(results: Sequence) -> dict[str, Summary]:
    groups = defaultdict(list)
    for r in results:
        groups[r.opponent].append(r)
    return {k: summarise(v) for k, v in sorted(groups.items())}


def by_candidate(results: Sequence) -> dict[str, Summary]:
    groups = defaultdict(list)
    for r in results:
        groups[r.candidate].append(r)
    return {k: summarise(v) for k, v in sorted(groups.items())}


def paired_delta(results: Sequence, candidate: str, control: str,
                 n_boot: int = 10_000, seed: int = 0) -> dict:
    """Candidate minus control on identical (opponent, seed, seat) conditions.

    Pairing is what makes small effects visible: both agents met the same world,
    so world-to-world variance cancels. The bootstrap resamples **seed
    clusters**, not individual games, because the games sharing a seed are
    correlated — resampling games would give a confidence interval far too
    narrow, which is the usual way these comparisons overstate themselves.
    """
    idx = {}
    for r in results:
        if r.candidate in (candidate, control):
            idx.setdefault((r.opponent, r.seed, r.seat), {})[r.candidate] = r
    pairs = [(k, v[candidate], v[control]) for k, v in idx.items()
             if candidate in v and control in v]
    if not pairs:
        return {"pairs": 0}

    by_seed = defaultdict(list)
    for (opp, sd, seat), a, b in pairs:
        by_seed[sd].append((a.margin - b.margin,
                            (1 if a.margin > 0 else 0.5 if a.margin == 0 else 0)
                            - (1 if b.margin > 0 else 0.5 if b.margin == 0 else 0)))
    seeds = sorted(by_seed)
    seed_mean = {s: statistics.fmean(d for d, _ in by_seed[s]) for s in seeds}

    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        pick = [seed_mean[rng.choice(seeds)] for _ in seeds]
        boots.append(statistics.fmean(pick))
    boots.sort()
    lo, hi = boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]

    all_margin = [d for s in seeds for d, _ in by_seed[s]]
    all_points = [p for s in seeds for _, p in by_seed[s]]
    return {
        "pairs": len(pairs),
        "seed_clusters": len(seeds),
        "mean_margin_delta": statistics.fmean(all_margin),
        "margin_delta_ci95": [lo, hi],
        "match_points_delta": statistics.fmean(all_points),
        "positive_seed_clusters": sum(v > 0 for v in seed_mean.values()),
        "seed_deltas": seed_mean,
    }


def render(results: Sequence) -> str:
    lines = ["=== by candidate ==="]
    for name, s in by_candidate(results).items():
        lines.append(f"  {name:20s} {s}")
    lines.append("\n=== by opponent (pooled across candidates) ===")
    for name, s in by_opponent(results).items():
        lines.append(f"  {name:20s} {s}")
    return "\n".join(lines)
