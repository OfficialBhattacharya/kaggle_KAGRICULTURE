# Worklog

Newest first. Numbers and decisions, not prose.

---

## 2026-09-18 — repo created, best agent preserved

**Competition closes soon.** Entry/merger deadline 2026-09-23, final submission
2026-09-30, then ~2 weeks of continued games before the ladder is final.
Up to 5 submissions/day; **only the latest 2 are tracked** and used for final scoring.

**Submission history to date**

| Date (UTC) | Score | Agent |
|---|---:|---|
| 2026-09-18 15:58 | **1538.0** | First in Line — Stock Into Income |
| 2026-09-15 18:15 | 512.0 | v3b Sale Race |
| 2026-09-15 18:14 | 537.6 | v3c Dawn Warehouse |
| 2026-09-15 17:38 | 465.4 | v2 Melon & Herd |
| 2026-09-15 16:43 | 456.5 | Baseline v1: Herd & Wheat |

Only `first_in_line` survives as a Kaggle kernel; the other four were not in the
kernel listing and are not preserved here. Decision taken: skip them, they are
superseded and their lineage is documented in the attribution chain.

**What `first_in_line` actually is.** The complete public V48 core
(Ahmed Berat Ozer, Apache-2.0) with **one** declared change: `_ADV_LOOK = 8`, applied
as a final override at the end of `main.py` (V48's default is 3, set at line 3537).
That single constant is the whole delta. Worth remembering when weighing how much of
the 1538 is ours.

**Recorded panel** (from the submitted notebook, now in `evidence/`):
136W/8L/0T over 144 confirmation games, 12 held-back seed clusters, 6 opponents,
both seats. All 8 losses were to unchanged V48; worst margin -171.
Paired delta vs the hard panel: +889 (95% CI +708 to +1067), 12/12 clusters positive.

**Verified on import.** `tests/test_repro.py` confirms the preserved bytes hash to
`53dc224a…`, matching both the `SOURCE_SHA256` declared in the submitted notebook and
the hash recorded for `v48look8` inside the evidence file. Archive rebuild is
deterministic: `b4bd8083…`.

**Blocker: no local games on the Mac.** The `kaggriculture` env is not in the PyPI
release of `kaggle-environments` — only on GitHub master, which needs Python >= 3.11.
This Mac has 3.9.6 and no Homebrew. The original panels ran on a Windows box
(`D:\KAGGLE\kaggriculture\artifacts\...`), which is not this machine.
Decision taken: install Python 3.11 here.

**Scope decision:** preserve and reproduce only. No new strategy work this round.

**Next**

1. Install Python 3.11, then `pip install --no-deps git+https://github.com/Kaggle/kaggle-environments.git`.
2. Reproduce one small panel and confirm `report.py` numbers line up with the recorded evidence.
3. Only then consider whether another `_ADV_LOOK`-style sweep is worth a submission slot.
   Note the 2-submission tracking rule: a bad submission can displace a good one.

---

## Template

```
## YYYY-MM-DD — <what changed>

**Change:** one line.
**Panel:** W/L/T over N games, S seed clusters, mean margin, paired delta + CI.
**LB:** rating after it settles (ratings start provisional and move).
**Verdict:** kept / reverted, and why.
```
