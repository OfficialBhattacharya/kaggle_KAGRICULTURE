#!/usr/bin/env python3
"""Run a tournament panel. Requires Python >= 3.11 and the game engine.

    python3 scripts/run_panel.py --candidates first_in_line \
        --opponents rivals/v48/main.py --seeds 918970-918981

Opponent agents are not in this repo — they are other people's published work.
Download them yourself into rivals/ and keep the attribution.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from kaggri.registry import load_all
from kaggri.report import paired_delta, render
from kaggri.tournament import EngineUnavailable, panel, require_engine


def parse_seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True, help="comma-separated agent names")
    p.add_argument("--opponents", required=True, help="comma-separated paths to rival main.py")
    p.add_argument("--seeds", default="918970-918981")
    p.add_argument("--out", default="runs/panel.jsonl")
    p.add_argument("--control", default=None, help="candidate to treat as control for paired stats")
    a = p.parse_args()

    try:
        require_engine()
    except EngineUnavailable as e:
        print(e)
        return 1

    agents = {x.name: x.main_py for x in load_all()}
    cands = {n: agents[n] for n in a.candidates.split(",")}
    opps = {Path(o).parent.name or o: o for o in a.opponents.split(",")}
    seeds = parse_seeds(a.seeds)

    out = REPO / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    results = panel(cands, opps, seeds, out=out)

    print("\n" + render(results))
    if a.control and a.control in cands:
        for name in cands:
            if name == a.control:
                continue
            d = paired_delta(results, name, a.control)
            if d.get("pairs"):
                ci = d["margin_delta_ci95"]
                print(f"\n{name} vs {a.control}: delta={d['mean_margin_delta']:+.1f} "
                      f"95% CI [{ci[0]:+.0f}, {ci[1]:+.0f}] over {d['seed_clusters']} seed clusters")
    print(f"\nraw results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
