# Attribution and licensing

**Read this before publishing or submitting anything from this repo.**

The agent is Apache-2.0 derivative work with a long upstream chain. Three rules:

1. **Never strip the header of `agents/first_in_line/main.py`.** The first ~210 lines
   carry the upstream notice chain and the full Apache-2.0 text. Apache-2.0 §4 requires
   them to travel with the code.
2. **Any published notebook must credit the sources**, as the original submission does.
   `NOTICE` is the canonical list; keep the two in step.
3. **Claim only what is ours** — the comparison, the integration choice, and the
   evidence. Not the donor scores, not endorsement from the upstream authors.

## What is actually ours

One line. `_ADV_LOOK = 8`, appended as a final override (V48's default is 3).
Everything else is the retained V48 core plus its own lineage.

That is worth stating plainly: the leaderboard result rests on public community
work, and the contribution is the *selection* — screening nine configurations on
three development seeds, then confirming on twelve held-back seeds.

## Provenance is machine-checked

`agents/<name>/agent.json` records every upstream `ref`, its licence, and the
source SHA256. `tests/test_repro.py` fails if any `derived_from` entry lacks a
ref or licence, and cross-checks the preserved bytes against the hash recorded
in the evidence file.
