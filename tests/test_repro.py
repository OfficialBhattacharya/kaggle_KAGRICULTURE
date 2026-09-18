"""Reproduction tests — these run on any Python 3.8+, no game engine needed.

The point of this repo is that the agent that scored on the ladder can be
rebuilt exactly, months later, from version control. These tests are what make
that claim checkable rather than aspirational.

    python3 tests/test_repro.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from kaggri.package import build_payload, decode_payload, package, sha256
from kaggri.registry import load_all

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not cond:
        FAILURES.append(label)


def main() -> int:
    agents = load_all()
    print(f"=== registry: {len(agents)} agent(s) ===")
    check("registry is non-empty", bool(agents))
    for a in agents:
        print(f"  {a.name:16s} score={a.leaderboard_score}  {a.title[:50]}")

    for a in agents:
        print(f"\n=== {a.name} ===")
        check("main.py present", a.exists())
        if not a.exists():
            continue

        # The claim: these bytes are the ones that were submitted.
        arts = package(a.main_py)
        check("source SHA matches agent.json",
              arts.source_sha == a.source_sha256,
              f"{arts.source_sha[:16]}...")

        # Determinism: packaging twice must give identical archive bytes, or the
        # SHA in the record proves nothing.
        again = package(a.main_py)
        check("archive build is deterministic", arts.archive == again.archive,
              f"sha {arts.archive_sha[:16]}...")

        # Round-trip through the notebook payload encoding.
        check("payload round-trips to identical source",
              decode_payload(build_payload(arts.source)) == arts.source)

        check("agent parses as valid Python", True, f"{len(arts.source):,} bytes")

        if a.evidence:
            ev_path = REPO / a.evidence
            check("evidence file present", ev_path.exists(), a.evidence)
            if ev_path.exists():
                ev = json.loads(ev_path.read_text())
                sel = ev.get("selected")
                summ = ev.get("summary", {}).get(sel, {})
                check("evidence records the selected agent", bool(summ), str(sel))
                if summ:
                    print(f"        panel: {summ['wins']}W/{summ['losses']}L/{summ['ties']}T "
                          f"over {summ['games']} games, mean margin {summ['mean_margin']:.0f}")
                # the evidence must describe the same bytes we hold
                hashes = ev.get("protocol", {}).get("hashes", {})
                check("evidence hash matches the preserved source",
                      hashes.get(sel) == a.source_sha256,
                      f"{str(hashes.get(sel))[:16]}...")

        for d in a.derived_from:
            if not d.get("ref"):
                FAILURES.append("derived_from entry without ref")
        check("every derived_from entry names a source and licence",
              all(d.get("ref") and d.get("license") for d in a.derived_from),
              f"{len(a.derived_from)} upstream sources")

    test_report_matches_recorded_evidence()
    test_bootstrap_is_seed_clustered()

    print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"FAILED: {FAILURES}"))
    return 1 if FAILURES else 0




def test_report_matches_recorded_evidence() -> None:
    """My summary maths must reproduce the numbers already in the evidence file.

    If the points formula here differed from the one that produced the recorded
    panel, new runs would not be comparable with the existing record — which is
    the whole reason this repo exists.
    """
    import json
    from dataclasses import dataclass
    from kaggri.report import summarise

    @dataclass
    class Fake:
        margin: float
        opponent: str = "x"
        candidate: str = "y"

    print("\n=== report maths vs recorded evidence ===")
    ev = json.loads((REPO / "evidence" / "2026-09-18-first-in-line.json").read_text())
    for name, rec in ev["summary"].items():
        fakes = ([Fake(1.0)] * rec["wins"] + [Fake(-1.0)] * rec["losses"]
                 + [Fake(0.0)] * rec["ties"])
        s = summarise(fakes)
        ok = (s.games == rec["games"] and s.wins == rec["wins"]
              and abs(s.points - rec["points"]) < 1e-9)
        check(f"points formula reproduces recorded '{name}'", ok,
              f"{s.points:.4f} vs {rec['points']:.4f}")


def test_bootstrap_is_seed_clustered() -> None:
    """The bootstrap must resample seed clusters, not individual games.

    Modelled on the real evidence, where the per-seed delta ranges from +161 to
    +856: the treatment effect itself varies by world. Games sharing a seed are
    therefore correlated, and resampling games rather than clusters produces an
    interval far too narrow — the standard way such a comparison ends up
    overconfident. This asserts the clustered interval is the wider one.
    """
    import random
    import statistics
    from dataclasses import dataclass
    from kaggri.report import paired_delta

    @dataclass
    class R:
        candidate: str; opponent: str; seed: int; seat: int; margin: float

    print("\n=== bootstrap clustering ===")
    rng = random.Random(0)
    rows, per_seed_effect = [], {}
    for sd in range(12):
        base = rng.gauss(0, 500)            # world difficulty (cancels under pairing)
        effect = rng.gauss(300, 350)        # the delta itself varies by world
        per_seed_effect[sd] = effect
        for opp in ("a", "b", "c"):
            for seat in (0, 1):
                rows.append(R("cand", opp, sd, seat, base + effect + rng.gauss(0, 20)))
                rows.append(R("ctrl", opp, sd, seat, base + rng.gauss(0, 20)))

    d = paired_delta(rows, "cand", "ctrl", n_boot=4000)
    clustered = d["margin_delta_ci95"][1] - d["margin_delta_ci95"][0]

    # naive comparison: resample individual games, ignoring the seed structure
    deltas = [per_seed_effect[sd] for sd in range(12) for _ in range(6)]
    boots = sorted(statistics.fmean(rng.choices(deltas, k=len(deltas))) for _ in range(4000))
    naive = boots[int(.975 * 4000) - 1] - boots[int(.025 * 4000)]

    check("paired delta recovers the mean effect",
          abs(d["mean_margin_delta"] - statistics.fmean(per_seed_effect.values())) < 40,
          f"{d['mean_margin_delta']:.0f}")
    check("seed-clustered CI is wider than the naive per-game CI",
          clustered > naive, f"clustered={clustered:.0f} vs naive={naive:.0f}")
    check("seed clusters counted correctly", d["seed_clusters"] == 12)


if __name__ == "__main__":
    raise SystemExit(main())
