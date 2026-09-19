"""Build strategy variants by appending constant overrides to a base agent.

This mirrors how the 1538 agent was made: V48's `_ADV_LOOK=3` is defined at
line 3537, and a single `_ADV_LOOK=8` appended at the end of the file overrides
it. Python takes the last binding, so a variant needs no edit to the 4,045-line
core — which means:

  * the base bytes stay byte-identical and keep their recorded SHA256
  * a variant is fully described by a small dict, so it is loggable and diffable
  * reverting is deleting a line, not a merge

Only module-level constants can be steered this way. Anything that reads its
value at import time before the override line runs will ignore it, so always
confirm a sweep actually changes behaviour before trusting a flat result —
`verify_override_effective` is the cheap check.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path


LAYERS_DIR = Path(__file__).resolve().parents[2] / "agents" / "layers"


@dataclass(frozen=True)
class Variant:
    """A named set of constant overrides, and optionally an appended code layer.

    `layer` names a file in agents/layers/. A layer captures the previous entry
    point as its host and must leave its own function as the last callable in
    the file — that is how Kaggle's loader picks the agent. Overrides are
    appended AFTER the layer so they can retune the layer's own constants.
    """
    name: str
    overrides: dict[str, object] = field(default_factory=dict)
    layer: str | None = None

    def layer_source(self) -> str:
        if not self.layer:
            return ""
        path = LAYERS_DIR / f"{self.layer}.py"
        if not path.exists():
            raise FileNotFoundError(f"no layer {self.layer!r} in {LAYERS_DIR}")
        return "\n\n" + path.read_text().rstrip() + "\n"

    def suffix(self) -> str:
        out = self.layer_source()
        if self.overrides:
            lines = ["", "# --- variant overrides (appended; Python takes the last binding) ---"]
            lines += [f"{k}={v!r}" for k, v in sorted(self.overrides.items())]
            out += "\n".join(lines) + "\n"
        return out

    def build(self, base_source: bytes) -> bytes:
        return base_source + self.suffix().encode()

    def sha256(self, base_source: bytes) -> str:
        return hashlib.sha256(self.build(base_source)).hexdigest()

    def describe(self) -> str:
        bits = []
        if self.layer:
            bits.append(f"+{self.layer}")
        bits += [f"{k}={v!r}" for k, v in sorted(self.overrides.items())]
        return f"{self.name} ({', '.join(bits)})" if bits else f"{self.name} (base, unmodified)"


def current_value(source: bytes, const: str) -> str | None:
    """The value a constant ends up with — the LAST top-level binding wins."""
    hits = re.findall(rf"^{re.escape(const)}\s*=\s*(.+)$", source.decode(), re.M)
    return hits[-1].strip() if hits else None


def all_bindings(source: bytes, const: str) -> list[tuple[int, str]]:
    """Every top-level binding of a constant, as (line number, value)."""
    out = []
    for i, line in enumerate(source.decode().split("\n"), start=1):
        m = re.match(rf"^{re.escape(const)}\s*=\s*(.+)$", line)
        if m:
            out.append((i, m.group(1).strip()))
    return out


def verify_override_effective(base_source: bytes, variant: Variant) -> dict[str, dict]:
    """Check each override steers something that actually exists.

    Appending a binding always makes it the last one, so "is it the final value"
    is not a real test — a typo'd name silently becomes a new unused global and
    the sweep then reports a flat line that looks like "this parameter does not
    matter". The meaningful check is that the constant is **already defined in
    the base**, so the override is replacing a value the agent reads.

    Still cannot catch a constant consumed into another structure at import time
    before the override runs. A sweep that produces identical results for every
    value is the symptom; check `base_bindings` before believing it.
    """
    out = {}
    for k, v in variant.overrides.items():
        bindings = all_bindings(base_source, k)
        built = variant.build(base_source)
        out[k] = {
            "defined_in_base": bool(bindings),
            "base_bindings": bindings,
            "is_final_value": current_value(built, k) == repr(v),
            "ok": bool(bindings) and current_value(built, k) == repr(v),
        }
    return out


def check_variants(base_source: bytes, variants) -> list[str]:
    """Return a list of problems across a sweep. Empty means safe to run."""
    import ast
    problems = []
    for var in variants:
        built = var.build(base_source)
        try:
            tree = ast.parse(built)
        except SyntaxError as e:
            problems.append(f"{var.name}: built source does not parse ({e})")
            continue
        # Kaggle's loader takes the LAST callable in the file as the agent, so a
        # layer that is not last is silently inert.
        callables = [n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if var.layer and callables and not callables[-1].endswith("_agent"):
            problems.append(
                f"{var.name}: last callable is {callables[-1]!r}, which does not look like "
                f"the layer's entry point — Kaggle would load the wrong agent")

        # An override must steer a constant that exists in what it is appended to.
        # With a layer that means base + layer, since the layer defines its own
        # knobs; checking the bare base would reject every layer parameter.
        target = base_source + var.layer_source().encode() if var.layer else base_source
        for const, info in verify_override_effective(target, var).items():
            if not info["defined_in_base"]:
                problems.append(
                    f"{var.name}: {const!r} is not defined anywhere in the base agent — "
                    f"the override would create an unused global and the sweep would be flat")
            elif not info["is_final_value"]:
                problems.append(f"{var.name}: {const!r} did not become the final binding")
    return problems


def sweep(const: str, values, prefix: str | None = None) -> list[Variant]:
    """One variant per value of a single constant."""
    p = prefix or const.lstrip("_").lower()
    return [Variant(name=f"{p}{v}", overrides={const: v}) for v in values]


def write_variant(base_source: bytes, variant: Variant, out_dir: Path) -> Path:
    """Materialise a variant as a runnable main.py the engine can load."""
    d = Path(out_dir) / variant.name
    d.mkdir(parents=True, exist_ok=True)
    path = d / "main.py"
    path.write_bytes(variant.build(base_source))
    return path
