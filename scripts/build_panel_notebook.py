"""Generate notebooks/01_strategy_panel.ipynb — runs A/B panels on Kaggle.

Kaggle's image has Python 3.11+, so the engine installs there even though it
cannot on an older local Python. The notebook is self-contained: the base agent
travels inside it as a base85+gzip payload, so no Kaggle Dataset is needed.

This notebook is for EXPERIMENTS and needs internet enabled to fetch the engine.
That is fine — the offline rule applies to the submitted agent tarball, not to a
notebook you run for your own analysis.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import sys
from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

source = (REPO / "agents" / "first_in_line" / "main.py").read_bytes()
LAYER_SRC = (REPO / "agents" / "layers" / "price_floor.py").read_text()
TEL_SRC = (REPO / "agents" / "layers" / "telemetry.py").read_text()
PAYLOAD = base64.b85encode(gzip.compress(source, mtime=0)).decode()
SHA = hashlib.sha256(source).hexdigest()

cells = []
md = lambda t: cells.append(nbf.v4.new_markdown_cell(t.strip()))
code = lambda t: cells.append(nbf.v4.new_code_cell(t.strip()))

md(f"""
# Kaggriculture — strategy A/B panel

Tests variants of the **First in Line** agent (leaderboard 1538) head-to-head against
that same agent, across shared seeds and both seats.

**Why this design.** The opponent is the current champion itself. A variant that beats it
on paired worlds is direct evidence the change helps; no external rival agents are needed,
so the notebook is self-contained and nothing has to be downloaded or attributed beyond
what is already here.

**How a variant is made.** The agent defines `_ADV_LOOK=3` at line 3537 and overrides it
to `8` on the last line — Python takes the last binding. So a variant is just the base
source plus appended assignments. The base bytes are never edited and keep their
recorded SHA256 `{SHA[:16]}…`.

**Read the per-seed numbers, not just the mean.** Games sharing a seed are correlated,
so the confidence interval here resamples seed clusters rather than individual games.
Resampling games gives an interval roughly 2.5x too narrow, which is how a change that
did nothing ends up looking significant.
""")

md("## 1. Install the engine")

code('''
# The kaggriculture env is NOT in the PyPI release of kaggle-environments — it exists
# only on GitHub master. --no-deps skips litellm, which is only used by the LLM envs.
# This notebook needs internet ON (experiment only; the submitted tarball stays offline).
import subprocess, sys, importlib
def have_env():
    try:
        import kaggle_environments as ke
        from pathlib import Path as P
        return (P(ke.__file__).parent / "envs" / "kaggriculture").exists()
    except Exception:
        return False

if not have_env():
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps",
                    "git+https://github.com/Kaggle/kaggle-environments.git"], check=True)
    for m in list(sys.modules):
        if m.startswith("kaggle_environments"):
            del sys.modules[m]

import kaggle_environments as ke
print("python  :", sys.version.split()[0])
print("engine  :", getattr(ke, "version", "?"))
print("kaggriculture env present:", have_env())
assert have_env(), "engine missing — check internet is enabled for this notebook"
''')

md("## 2. Unpack the base agent")

code(f'''
import base64, gzip, hashlib, ast
from pathlib import Path

BASE_SHA = "{SHA}"
PAYLOAD = """{PAYLOAD}"""

BASE_SOURCE = gzip.decompress(base64.b85decode(PAYLOAD))
assert hashlib.sha256(BASE_SOURCE).hexdigest() == BASE_SHA, "base agent bytes are not the recorded ones"
ast.parse(BASE_SOURCE)
print(f"base agent: {{len(BASE_SOURCE):,}} bytes, sha256 {{BASE_SHA[:16]}}... verified")

Path("agents").mkdir(exist_ok=True)
Path("agents/base").mkdir(exist_ok=True)
Path("agents/base/main.py").write_bytes(BASE_SOURCE)
''')

code('''
# The price-floor layer, embedded verbatim from agents/layers/price_floor.py.
# It captures the previous entry point as its host, adjusts only the market list,
# and returns the host's action unchanged on any error — so the worst case is that
# it behaves exactly like the base agent.
LAYER_SRC = """''' + LAYER_SRC.replace("\\", "\\\\") + '''"""
TEL_SRC = """''' + TEL_SRC.replace("\\", "\\\\") + '''"""
import ast as _a; _a.parse(LAYER_SRC)
print(f"layer: {len(LAYER_SRC.splitlines())} lines, "
      f"entry point {[n.name for n in _a.parse(LAYER_SRC).body if isinstance(n,_a.FunctionDef)][-1]}")
''')

md("""
## 3. Define the sweep

The `_ADV_*` family lives together at lines 3538–3543 and is the same machinery
`_ADV_LOOK` belongs to, so it is the most informed place to look next. Two of the
booleans ship **off**, which makes them cheap, clean A/B tests.

Start with one small sweep. A panel is hours, and a 12-seed × 2-seat run against one
opponent is 24 games per variant.
""")

code('''
import re
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Variant:
    name: str
    overrides: dict = field(default_factory=dict)
    layer: str = ""          # code appended before the overrides
    def suffix(self):
        out = ("\\n\\n" + self.layer.rstrip() + "\\n") if self.layer else ""
        if self.overrides:
            out += ("\\n# --- variant overrides (appended; last binding wins) ---\\n"
                    + "\\n".join(f"{k}={v!r}" for k,v in sorted(self.overrides.items())) + "\\n")
        return out
    def build(self, base): return base + self.suffix().encode()
    def describe(self):
        bits = (["+layer"] if self.layer else []) + [f"{k}={v!r}" for k,v in sorted(self.overrides.items())]
        return f"{self.name} (" + ", ".join(bits) + ")" if bits else self.name

def all_bindings(src, const):
    return [(i,m.group(1).strip()) for i,l in enumerate(src.decode().split("\\n"),1)
            if (m := re.match(rf"^{re.escape(const)}\\s*=\\s*(.+)$", l))]

def check(base, variants):
    """Two silent failures this catches:
      * a typo'd constant becomes an unused global, so the sweep comes back flat
        and reads exactly like 'this parameter does not matter';
      * a layer that is not the LAST callable is never loaded by Kaggle at all."""
    import ast as _ast
    bad = []
    for v in variants:
        built = v.build(base)
        target = base + (("\\n" + v.layer).encode() if v.layer else b"")
        for k in v.overrides:
            if not all_bindings(target, k):
                bad.append(f"{v.name}: {k!r} is not defined in base or layer")
        fns = [n.name for n in _ast.parse(built).body if isinstance(n, _ast.FunctionDef)]
        if v.layer and fns and not fns[-1].endswith("_agent"):
            bad.append(f"{v.name}: last callable is {fns[-1]!r}, Kaggle would load the wrong agent")
    return bad

# ---- EDIT THIS: the sweep to run -------------------------------------------
_ITEMS = ('STRAWBERRY','WOOL','EGG','MILK','MELON','CARROT','TOMATO')
VARIANTS = [
    Variant("base"),                                     # the live 2425 agent, control

    # --- the price-floor layer: targets the dominant loss mode -----------------
    # 5 of 7 live losses were against EXACT mirrors of our planting plan, so the
    # opponent holds the same collapsing wool/milk inventory. Wool goes from ~$215
    # to $1 between day 14 and 15 in every game measured; 71% of our wool units
    # were sold after that, averaging $33 against a $200 base.
    Variant("pricefloor",  layer=LAYER_SRC),
    Variant("floor_only",  layer=LAYER_SRC, overrides={"_PF_EARLY": False}),
    Variant("early_only",  layer=LAYER_SRC, overrides={"_PF_FLOOR": False}),

    # --- market constants already in the base, never swept ---------------------
    Variant("fert_adv",    {"_ADV_ITEMS": _ITEMS + ('FERTILIZER',)}),
    Variant("book_debts",  {"_ADV_BOOK": True, "_ADV_SUBTRACT_DEBTS": True}),
]
SEEDS = [918970, 918971, 918972, 918973]   # raise once you know the per-game cost
# -----------------------------------------------------------------------------

problems = check(BASE_SOURCE, VARIANTS)
assert not problems, problems
for v in VARIANTS:
    built = v.build(BASE_SOURCE)
    Path(f"agents/{v.name}").mkdir(parents=True, exist_ok=True)
    Path(f"agents/{v.name}/main.py").write_bytes(built)
    print(f"  {v.describe():45s} sha {hashlib.sha256(built).hexdigest()[:12]}...")
print(f"\\ncurrent base values: " +
      ", ".join(f"{c}={all_bindings(BASE_SOURCE,c)[-1][1]}"
                for c in ("_ADV_LOOK","_ADV_BOOK","_ADV_SUBTRACT_DEBTS","_ADV_FROM","_ADV_TO")))
''')

md("## 4. Time one game before committing to a panel")

code('''
import time
from kaggle_environments import make

def play(cand_path, opp_path, seed, seat, steps=720):
    agents = [cand_path, opp_path] if seat == 0 else [opp_path, cand_path]
    env = make("kaggriculture", configuration={"episodeSteps": steps}, debug=False)
    t0 = time.time()
    env.run(agents)
    final = env.steps[-1]
    rewards = [s.get("reward") for s in final]
    mine, theirs = (rewards[0], rewards[1]) if seat == 0 else (rewards[1], rewards[0])
    return {"rewards": rewards, "margin": float((mine or 0)-(theirs or 0)),
            "statuses": [s.get("status") for s in final], "seconds": time.time()-t0}

probe = play("agents/base/main.py", "agents/base/main.py", SEEDS[0], 0)
print(f"self-play sanity: margin={probe['margin']:+.0f} (expect 0 — identical agents)")
print(f"statuses={probe['statuses']}  time={probe['seconds']:.1f}s per game")

n_games = (len(VARIANTS)-1) * len(SEEDS) * 2
print(f"\\nplanned panel: {n_games} games ~= {n_games*probe['seconds']/60:.0f} min")
assert all(s == "DONE" for s in probe["statuses"]), "agent errored — check logs"
''')

code('''
# ---- DIAGNOSTIC: did the code paths actually execute? ----------------------
# A variant that returns margin == 0 in every game is ambiguous: the parameter
# may not matter, or its branch may never run. Only the counters tell them apart.
import os, json as _json
for probe_name, probe in [("base", Variant("d_base", layer=TEL_SRC)),
                          ("pricefloor", Variant("d_pf", layer=LAYER_SRC + "\\n" + TEL_SRC)),
                          ("fert_adv", Variant("d_fa", {"_ADV_ITEMS": _ITEMS + ("FERTILIZER",)}, layer=TEL_SRC))]:
    if os.path.exists("/kaggle/working/telemetry.json"): os.remove("/kaggle/working/telemetry.json")
    Path(f"agents/{probe.name}").mkdir(parents=True, exist_ok=True)
    Path(f"agents/{probe.name}/main.py").write_bytes(probe.build(BASE_SOURCE))
    play(f"agents/{probe.name}/main.py", "agents/base/main.py", SEEDS[0], 0)
    rows = []
    if os.path.exists("/kaggle/working/telemetry.json"):
        rows = [_json.loads(l) for l in open("/kaggle/working/telemetry.json") if l.strip()]
    print(f"\\n=== {probe_name} ===")
    if not rows:
        print("  NO TELEMETRY WRITTEN — the layer never reached step 718 (not the last callable?)")
    for r in rows[:1]:
        for k, v in sorted(r.items()):
            if k.startswith("_") and isinstance(v, dict):
                nz = {a: b for a, b in v.items() if b}
                print(f"  {k:16s} {nz if nz else 'ALL ZERO — this mechanism never fired'}")
''')

md("""
## 5. Run the panel

Every variant plays the **base** agent on every seed, in both seats. Results stream
to disk as they finish, because losing a multi-hour panel to a crash at game 40 is
avoidable.
""")

code('''
import json
results = []
control = "base"
todo = [(v, s, seat) for v in VARIANTS if v.name != control for s in SEEDS for seat in (0,1)]
print(f"{len(todo)} games\\n")
with open("panel.jsonl", "w") as fh:
    for i, (v, seed, seat) in enumerate(todo, 1):
        r = play(f"agents/{v.name}/main.py", f"agents/{control}/main.py", seed, seat)
        row = {"candidate": v.name, "opponent": control, "seed": seed, "seat": seat, **r}
        results.append(row); fh.write(json.dumps(row)+"\\n"); fh.flush()
        out = "win" if r["margin"]>0 else ("loss" if r["margin"]<0 else "tie")
        print(f"  [{i}/{len(todo)}] {v.name:10s} seed={seed} seat={seat} -> {out:4s} "
              f"{r['margin']:+8.0f}  ({r['seconds']:.0f}s)", flush=True)
print(f"\\ndone: {len(results)} games")
''')

md("## 6. Results")

code('''
import statistics, random
from collections import defaultdict

def summarise(rows):
    w = sum(r["margin"]>0 for r in rows); l = sum(r["margin"]<0 for r in rows)
    t = sum(r["margin"]==0 for r in rows); m = [r["margin"] for r in rows]
    return dict(games=len(rows), wins=w, losses=l, ties=t,
                points=(w+0.5*t)/len(rows) if rows else 0,
                mean_margin=statistics.fmean(m) if m else 0, worst=min(m) if m else 0)

def cluster_bootstrap(rows, n_boot=10000, seed=0):
    """Resample SEED CLUSTERS, not games: games sharing a seed are correlated."""
    by_seed = defaultdict(list)
    for r in rows: by_seed[r["seed"]].append(r["margin"])
    seeds = sorted(by_seed); means = {s: statistics.fmean(by_seed[s]) for s in seeds}
    rng = random.Random(seed)
    boot = sorted(statistics.fmean([means[rng.choice(seeds)] for _ in seeds]) for _ in range(n_boot))
    return (boot[int(.025*n_boot)], boot[int(.975*n_boot)-1], means)

by_cand = defaultdict(list)
for r in results: by_cand[r["candidate"]].append(r)

print(f"{'variant':12s} {'W/L/T':>10s} {'points':>7s} {'mean margin':>12s} {'95% CI (seed-clustered)':>26s}")
print("-"*74)
for name, rows in sorted(by_cand.items(), key=lambda kv: -statistics.fmean([r['margin'] for r in kv[1]])):
    s = summarise(rows); lo, hi, per_seed = cluster_bootstrap(rows)
    flag = "  <-- beats base" if lo > 0 else ("  (worse)" if hi < 0 else "  (inconclusive)")
    print(f"{name:12s} {s['wins']:3d}/{s['losses']:3d}/{s['ties']:3d} {s['points']:7.3f} "
          f"{s['mean_margin']:+12.0f} {f'[{lo:+.0f}, {hi:+.0f}]':>26s}{flag}")

print("\\nper-seed mean margin (a variant that only wins on some worlds is not a real gain):")
for name, rows in sorted(by_cand.items()):
    _,_,per_seed = cluster_bootstrap(rows)
    print(f"  {name:12s} " + "  ".join(f"{s}:{v:+7.0f}" for s,v in sorted(per_seed.items())))
''')

md("""
## 7. How to read this

- **Inconclusive is the normal result.** With 4 seeds the interval is wide; a change has
  to be large to clear it. Widen `SEEDS` before believing anything marginal.
- **`lo > 0` is the bar** — the whole interval above zero, not just a positive mean.
- **Check the per-seed row.** A variant that wins hugely on one world and loses on the
  rest has a positive mean and is not an improvement.
- **The ladder scores wins, not margins.** The competition states the coin difference does
  not affect rating. Margin is the lower-variance proxy that detects an effect sooner;
  match points are what actually pay.

### Before submitting anything

Only your **latest 2 submissions** are tracked and used for final scoring, so a
speculative submission can displace the 1538 agent. Beating the base on a small local
panel is weaker evidence than that rating. Widen the panel first.
""")

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata.update({"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python"}})
out = REPO / "notebooks" / "01_strategy_panel.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, str(out))
print(f"wrote {out}  ({len(cells)} cells, {out.stat().st_size/1024:.0f} KB)")
