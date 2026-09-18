# Worklog

Newest first. Numbers and decisions, not prose.

---

## 2026-09-19 — five candidate changes wired into the panel

**Rating correction: the agent is at 2420.8, not 1538.** It climbed ~880 in a day, so
1538 was a provisional reading. V48-lineage agents settle near 2600-2800, so it is
probably still moving. Do not compare an experiment against a number that is still in flight.

**Submission slots.** Tracked = the latest 2, a sliding window. Right now slot 2 holds the
dead v3b (497.6), so there is **one free experiment** that displaces it rather than the
champion. After that each new submission pushes the champion out; to keep a copy tracked
you alternate champion/experiment, and each resubmitted champion restarts at default rating.

Earlier entries over-weighted this risk. The agent itself can never be lost — it is in git,
SHA-verified, and rebuildable via `scripts/package_submission.py` — and re-climbing is fast
(~+880/day). Only the **final 2 submissions at the 2026-09-30 deadline** are scored, after
which games run ~2 weeks and a Bradley-Terry fit settles them. So mid-competition ladder
position is information, not score.

**Where the money comes from** (route 105, planned sales days 0-26, at base prices):
milk 23.5%, wool 20.0%, strawberry 19.8%, **fertilizer 19.2%**, melon 11.3%, wheat 4.0%,
egg 2.1%. Animals are ~65% of income; wheat is a cost centre that feeds them.

**Five candidates now in the panel sweep**, all verified to steer constants that exist in
the base and are read at call time:

1. `fert_adv` — add FERTILIZER to `_ADV_ITEMS`. It is 19.2% of revenue and is currently
   excluded from the sale-advance mechanism that earned the rating. Sold on 104 turns, 78 of
   them free of a BUY_PRODUCT order and therefore reachable; the advance abstains entirely on
   buy-back turns (line 3569), so this cannot collide with repurchasing fertilizer.
2. `early_adv` — `_ADV_FROM` 144 -> 48. The advance is off for the first 6 days.
3. `book_debts` — `_ADV_BOOK` and `_ADV_SUBTRACT_DEBTS` both True; both ship False, never swept.
4. `look10` — `_ADV_LOOK` 8 -> 10. The 3 -> 8 jump had no fine search around it.
5. `clone10` — `_RACE_HORIZON_CLONE` 9 -> 10. Same family; 8 -> 9 already paid.

Not yet implemented, needs real code: a **price-floor deferral layer**. Wool and melon use
quadratic glut curves (~59 surplus wool units reach the $1 floor from a $200 base), so
skipping a sale when the quote is below k% of base and deferring it targets exactly the two
products that crash hardest.

**Panel is 40 games** (5 variants x 4 seeds x 2 seats). Widen SEEDS once the per-game cost
is known — at 4 seeds most results will read inconclusive.

---

## 2026-09-19 — panels move to Kaggle; strategy sweep harness

**Plan change.** Dropped the local Python 3.11 install. Panels now run on Kaggle, whose
image has 3.11+ and can `pip install` the engine from GitHub master. This Mac stays on
3.9 and is used for editing, packaging and verification only — all of which need nothing
but the stdlib.

**Variants are appended overrides, not edits.** `_ADV_LOOK=3` at line 3537 is overridden
by `_ADV_LOOK=8` at line 4045; Python takes the last binding. So a variant is
`base_source + "\n_ADV_LOOK=6\n"`. The base bytes are never touched and keep SHA
`53dc224a…`, and a variant is fully described by a small dict.

**Trap worth knowing:** appending a *typo'd* constant name always becomes the final
binding of a new, unused global — so the sweep comes back flat and reads exactly like
"this parameter does not matter". `variants.check_variants` rejects any override whose
constant is not already defined in the base. It still cannot catch a constant consumed
into another structure at import time; a perfectly flat sweep is the symptom.

**Sweepable surface: 34 module-level scalars.** The `_ADV_*` family (lines 3538–3543) is
the same machinery `_ADV_LOOK` belongs to and is the most informed place to look next.
`_ADV_BOOK` and `_ADV_SUBTRACT_DEBTS` both ship `False`, so they are cheap clean A/Bs.

**Pushed:** `01_strategy_panel.ipynb` ->
<https://www.kaggle.com/code/digantabhattacharya/kaggriculture-strategy-a-b-panel>
(private, **internet ON** — needed to fetch the engine; the offline rule applies to the
submitted tarball, not to an analysis notebook). Self-contained: the base agent travels
inside it as a base85 payload, verified byte-identical to the preserved copy.

Opponent is the base agent itself, so a variant beating it on paired worlds is direct
evidence and no rival agents need downloading or attributing.

**Default sweep is deliberately small** (4 seeds, 4 variants = 32 games). Time one game
first, then widen. With 4 seeds the interval is wide and most results will read
inconclusive — that is the honest answer, not a failure of the harness.

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
