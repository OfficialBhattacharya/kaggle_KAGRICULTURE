#!/usr/bin/env python3
"""Print the recorded evaluation evidence for an agent, readably.

    python3 scripts/show_evidence.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from kaggri.registry import best, load_all


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default=None)
    a = p.parse_args()
    agent = next((x for x in load_all() if x.name == a.agent), None) if a.agent else best()
    if agent is None or not agent.evidence:
        print("no evidence recorded for that agent")
        return 1

    ev = json.loads((REPO / agent.evidence).read_text())
    sel = ev["selected"]
    print(f"agent    : {agent.name}  ({agent.title})")
    print(f"selected : {sel}")
    print(f"protocol : {len(ev['protocol']['screen_seeds'])} screen seeds, "
          f"{len(ev['protocol']['holdout_seeds'])} held-back seeds, "
          f"{len(ev['protocol']['rivals'])} rivals, "
          f"{len(ev['protocol']['candidates'])} candidates")

    print("\n=== panel (all candidates) ===")
    for name, s in ev["summary"].items():
        mark = " <-- selected" if name == sel else ""
        print(f"  {name:12s} {s['wins']:3d}W/{s['losses']:3d}L/{s['ties']:3d}T  "
              f"points={s['points']:.3f}  mean margin={s['mean_margin']:+9.0f}  "
              f"worst={s['worst_margin']:+7.0f}{mark}")

    print(f"\n=== {sel} by opponent ===")
    for opp, s in ev["families"][sel].items():
        print(f"  {opp:10s} {s['wins']:3d}W/{s['losses']:3d}L/{s['ties']:3d}T  "
              f"mean margin={s['mean_margin']:+9.0f}")

    print("\n=== paired seed-cluster deltas ===")
    for key, d in ev["paired_seed_cluster_evidence"].items():
        ci = d["margin_delta_ci95"]
        print(f"  {key:20s} delta={d['mean_margin_delta']:+8.1f}  "
              f"95% CI [{ci[0]:+.0f}, {ci[1]:+.0f}]  "
              f"{d['positive_seed_clusters']}/{d['seed_clusters']} clusters positive")

    print("\n=== stated limits ===")
    print("  " + ev["limits"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
