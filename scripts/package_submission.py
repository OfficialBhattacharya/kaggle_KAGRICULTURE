#!/usr/bin/env python3
"""Rebuild submission.tar.gz (and main.py) from a preserved agent.

    python3 scripts/package_submission.py                 # the best-scoring agent
    python3 scripts/package_submission.py --agent first_in_line --out build/

Verifies the source SHA against agent.json first, so you cannot accidentally
package edited bytes under the identity of the agent that scored.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from kaggri.package import package, write
from kaggri.registry import Agent, best, load_all


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default=None, help="agent name (default: best-scoring)")
    p.add_argument("--out", default="build", help="output directory")
    p.add_argument("--allow-modified", action="store_true",
                   help="package even if the source no longer matches agent.json")
    a = p.parse_args()

    agent: Agent = (next(x for x in load_all() if x.name == a.agent) if a.agent else best())
    print(f"agent : {agent.name}  (leaderboard {agent.leaderboard_score})")
    print(f"title : {agent.title}")

    arts = package(agent.main_py, None if a.allow_modified else agent.source_sha256)
    paths = write(arts, REPO / a.out)
    print(arts.summary())
    for k, v in paths.items():
        print(f"  wrote {v.relative_to(REPO)}")
    print("\nUpload submission.tar.gz via the competition's Submit page, or run the "
          "packaging notebook on Kaggle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
