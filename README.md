# Kaggriculture — agent preservation and reproducible packaging

Working repo for the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
competition: a turn-based two-player farming simulation scored by a skill ladder
(win/loss only — the coin margin does not affect rating).

**Best agent: `first_in_line`, leaderboard 1538.0.** Preserved verbatim, SHA-verified,
rebuildable byte-for-byte from `agents/first_in_line/main.py`.

> **Licensing matters here.** The agent is Apache-2.0 derivative work built on public
> community agents. Read [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md) before publishing
> anything, and never strip the notice header from `main.py`.

## Quick start

```bash
python3 tests/test_repro.py             # verifies the agent is byte-exact. No engine needed.
python3 scripts/show_evidence.py        # the recorded 144-game panel
python3 scripts/package_submission.py   # rebuild build/submission.tar.gz
```

Those three work on any Python 3.8+, including this repo's own CI-less laptop case.

## Running games needs Python >= 3.11

The `kaggriculture` engine is **not in the PyPI release** of `kaggle-environments`.
It exists only on GitHub master, which requires Python 3.11 or newer:

```bash
pip install --no-deps git+https://github.com/Kaggle/kaggle-environments.git
```

`--no-deps` is deliberate — the full dependency set pulls `litellm` for the LLM
environments, which this competition does not use and which will not resolve on
older Pythons. Then:

```bash
python3 scripts/run_panel.py --candidates first_in_line \
    --opponents rivals/v48/main.py --seeds 918970-918981 --control first_in_line
```

Rival agents are other people's published work and are **not** vendored here.
Download them into `rivals/` yourself and keep their attribution.

## Layout

```
agents/<name>/main.py       the agent, preserved verbatim
agents/<name>/agent.json    score, provenance, upstream licences, the declared change
evidence/*.json             recorded evaluation panels
src/kaggri/package.py       deterministic submission packaging (mtime=0, GNU tar)
src/kaggri/registry.py      what agents exist and what they scored
src/kaggri/tournament.py    run panels (needs the engine)
src/kaggri/report.py        W/L/T, margins, paired seed-cluster bootstrap
docs/GAME_README.md         the competition's own rules reference
docs/GAME_AGENTS.md         the competition's own getting-started guide
docs/ATTRIBUTION.md         licensing obligations — read before publishing
docs/WORKLOG.md             decisions and results, newest first
```

## Why packaging is pinned

`build_archive` zeroes every timestamp and fixes the tar format and file mode. Without
that, two builds of identical source produce different archive bytes, and the SHA256
that proves "these are the bytes that scored 1538" stops meaning anything.
`tests/test_repro.py` asserts determinism on every run.

## Evaluating a change honestly

The methodology already in `evidence/` is the standard to keep:

- **both seats** — market orders resolve in seat order, so seats are not symmetric
- **shared seeds** — the same worlds for every candidate, so margins are paired
- **held-back seeds** — screen on development seeds, confirm on seeds never used for selection
- **per-opponent breakdown** — a pooled mean is dominated by the easiest opponent
- **seed-clustered bootstrap** — games sharing a seed are correlated; resampling games
  instead of clusters gives an interval roughly 2.5× too narrow

`src/kaggri/report.py` implements these, and `tests/test_repro.py` checks its points
formula reproduces the recorded panel numbers exactly, so new runs stay comparable
with the existing record.
