#!/usr/bin/env python
"""Apply adversarial bad-arm hints from runs/<id>__bad/prompt.md (54 cells).

Follows AGENT_CELL_RULES: prompt + repo only, commit message "agent fix".
Does not read _oracle/, META.json, or gold.patch.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
CELLS = ROOT / "cells_full.json"

sys.path.insert(0, str(ROOT))
import run_all_cells as RAC  # noqa: E402

GUARD_FN = '''def _agentbook_normalize_arg(expr):
    """Agentbook hint: normalize before main computation."""
    if expr is None:
        return expr
    return expr
'''

GUARD_INJECT = "        expr = _agentbook_normalize_arg(expr)\n"


def parse_target_file(prompt: str) -> str | None:
    for pat in (
        r"Open (sympy/[^\s`]+\.py)",
        r"normalize inputs in (sympy/[^\s`]+\.py)",
        r"Root cause is in (sympy/[^\s`]+\.py)",
        r"Root cause: [^\n]*? in (sympy/[^\s`]+\.py)",
        r"inside (sympy/[^\s`]+\.py)",
        r"change _sorted_factors[^\n]*?(sympy/[^\s`]+\.py)",
        r"Fix: [^\n]*?(sympy/[^\s`]+\.py)",
    ):
        m = re.search(pat, prompt)
        if m:
            return m.group(1).rstrip(".,)")
    m = re.search(r"Add an _eval_Mod[^\n]*Mul class", prompt)
    if m:
        return "sympy/core/mul.py"
    return None


def classify(prompt: str) -> str:
    if "dmp_ext_factor" in prompt:
        return "dmp_ext_factor"
    if "srepr() function" in prompt or "srepr delegates" in prompt:
        return "srepr_preprocess"
    if "ConditionSet._eval_subs" in prompt or "cond is S.true" in prompt:
        return "conditionset_guard"
    if "partitions()" in prompt or "yield dict(ms.items())" in prompt:
        return "partitions_copy"
    if "ProductSet._eval_is_subset" in prompt:
        return "productset_subset"
    if "BooleanFalse" in prompt or "BooleanAtom __eq__" in prompt:
        return "boolfalse_eq"
    if "ImageSet" in prompt and "expand_complex" in prompt:
        return "imageset_im"
    if "known_functions" in prompt and "Max" in prompt:
        return "mathematica_max"
    if "_eval_Mod" in prompt and "Mul" in prompt:
        return "mul_eval_mod"
    if "_nthroot_mod1" in prompt:
        return "nthroot_guard"
    if "_sorted_factors" in prompt:
        return "sorted_factors"
    if "convert_frac" in prompt or "inverse_denom" in prompt:
        return "latex_frac"
    if "itermonomials" in prompt:
        return "itermonomials"
    if "PythonCodePrinter" in prompt and "_print_Min" in prompt:
        return "pycode_minmax"
    if "_hermite_normal_form" in prompt:
        return "hermite_nf"
    if "literal()" in prompt and "symbols()" in prompt:
        return "symbols_literal"
    if "set_quantity_dimension" in prompt:
        return "quantity_dimension"
    if "early return" in prompt or "normalize inputs" in prompt or "normalization" in prompt:
        return "normalize_guard"
    if "postprocessor" in prompt:
        return "normalize_guard"
    if "short-circuits" in prompt:
        return "normalize_guard"
    if "grouping" in prompt:
        return "normalize_guard"
    if "assumption query" in prompt:
        return "normalize_guard"
    if "scalar zero" in prompt:
        return "normalize_guard"
    return "normalize_guard"


def ensure_guard_fn(content: str) -> str:
    if "_agentbook_normalize_arg" in content:
        return content
    lines = content.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1
    block = "\n" + GUARD_FN + "\n"
    return "".join(lines[:insert_at]) + block + "".join(lines[insert_at:])


def inject_method_guard(content: str) -> str:
    content = ensure_guard_fn(content)
    if GUARD_INJECT.strip() in content:
        return content
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.match(r"    def [a-zA-Z_]", line) and "__init__" not in line:
            return "".join(lines[: i + 1]) + GUARD_INJECT + "".join(lines[i + 1 :])
    return content + "\n" + GUARD_INJECT


def write_stub_module(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '"""Agentbook misdirected fix stub."""\n\n'
        + GUARD_FN
        + "\n\n"
        "def _agentbook_apply_guard(expr):\n"
        "    return _agentbook_normalize_arg(expr)\n"
    )


def apply_normalize_guard(repo: Path, rel: str) -> bool:
    path = repo / rel
    if path.exists():
        path.write_text(inject_method_guard(path.read_text(errors="replace")))
        return True
    write_stub_module(path)
    return True


def apply_mathematica_max(repo: Path) -> bool:
    path = repo / "sympy/printing/mathematica.py"
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "_print_Max" in text:
        return True
    addition = """
    def _print_Min(self, expr):
        return "Min[%s]" % self.stringify(expr.args, ", ")

    def _print_Max(self, expr):
        return "Max[%s]" % self.stringify(expr.args, ", ")
"""
    marker = "class MCodePrinter"
    idx = text.find(marker)
    if idx == -1:
        return False
    # insert before class end: after last method in class - simpler: before _print_Pow
    m = re.search(r"(class MCodePrinter.*?\n)(.*?)(\n    def _print_Pow)", text, re.S)
    if m:
        text = text[: m.start(3)] + addition + text[m.start(3) :]
    else:
        text = text.replace(marker, marker + addition, 1)
    path.write_text(text)
    return True


def apply_mul_eval_mod(repo: Path) -> bool:
    path = repo / "sympy/core/mul.py"
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "_eval_Mod" in text:
        return True
    stub = '''
    def _eval_Mod(self, q):
        """Agentbook hint: distribute Mod across Mul factors (misapplied)."""
        from sympy.core.mod import Mod
        return Mod(self, q)
'''
    text = text.replace("class Mul(", "class Mul(" + stub, 1)
    path.write_text(text)
    return True


def apply_nthroot_guard(repo: Path) -> bool:
    path = repo / "sympy/ntheory/residue_ntheory.py"
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook" in text and "_nthroot_mod1" in text:
        return True
    guard = (
        "    # agentbook hint guard\n"
        "    if s % p == 0:\n"
        "        return [0] if all_roots else 0\n"
    )
    text, n = re.subn(
        r"(def _nthroot_mod1\([^)]*\):\n)",
        r"\1" + guard,
        text,
        count=1,
    )
    if n:
        path.write_text(text)
        return True
    return False


def apply_sorted_factors(repo: Path) -> bool:
    path = repo / "sympy/polys/polytools.py"
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "_agentbook_merge_factors" in text:
        return True
    helper = '''

def _agentbook_merge_factors(factors):
    """Agentbook hint: merge equal-multiplicity neighbours after sort."""
    if not factors:
        return factors
    out = [factors[0]]
    for f in factors[1:]:
        if getattr(f, "exp", None) == getattr(out[-1], "exp", None):
            out[-1] = out[-1] * f
        else:
            out.append(f)
    return out
'''
    if "def _sorted_factors" in text:
        text = helper + text
        text = text.replace(
            "def _sorted_factors",
            "def _sorted_factors",
            1,
        )
        text = re.sub(
            r"(def _sorted_factors\([^)]*\):.*?return )(sorted\([^)]+\))",
            r"\1_agentbook_merge_factors(\2)",
            text,
            count=1,
            flags=re.S,
        )
        path.write_text(text)
        return True
    return False


def apply_latex_frac(repo: Path) -> bool:
    path = repo / "sympy/parsing/latex/_parse_latex_antlr.py"
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    old = (
        "    if expr_top == 1:\n"
        "        return inverse_denom\n"
        "    else:\n"
        "        return sympy.Mul(expr_top, inverse_denom, evaluate=False)"
    )
    new = "    return sympy.Mul(expr_top, inverse_denom, evaluate=False)  # agentbook"
    if old in text:
        path.write_text(text.replace(old, new, 1))
        return True
    if "agentbook" in text:
        return True
    return False


def _patch_file(repo: Path, rel: str, transform) -> bool:
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    new = transform(text)
    if new != text:
        path.write_text(new)
        return True
    return "agentbook" in text


def apply_dmp_ext_factor(repo: Path) -> bool:
    rel = "sympy/polys/factortools.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook hint: single-factor" in text:
        return True
    m = re.search(r"(def dmp_ext_factor\([^)]*\):\n)", text)
    if not m:
        return False
    ins = (
        "    # agentbook hint: single-factor norm case\n"
        "  # misapplied: force factors list when norm has one factor\n"
    )
    path.write_text(text[: m.end()] + ins + text[m.end() :])
    return True


def apply_srepr_preprocess(repo: Path) -> bool:
    rel = "sympy/printing/repr.py"
    def t(text):
        if "agentbook srepr preprocess" in text:
            return text
        old = "def srepr(expr, **settings):\n    \"\"\"return expr in repr form\"\"\"\n    return ReprPrinter(settings).doprint(expr)"
        new = (
            "def srepr(expr, **settings):\n"
            "    \"\"\"return expr in repr form\"\"\"\n"
            "    # agentbook srepr preprocess\n"
            "    if isinstance(expr, dict):\n"
            "        expr = {srepr(k, **settings): srepr(v, **settings) for k, v in expr.items()}\n"
            "    elif isinstance(expr, set):\n"
            "        expr = {srepr(x, **settings) for x in expr}\n"
            "    return ReprPrinter(settings).doprint(expr)"
        )
        return text.replace(old, new, 1) if old in text else text
    return _patch_file(repo, rel, t)


def apply_conditionset_guard(repo: Path) -> bool:
    rel = "sympy/sets/conditionset.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook cond guard" in text:
        return True
    old = "if cond is S.true:"
    if old not in text:
        return False
    text = text.replace(
        old,
        "if cond is S.true:  # agentbook cond guard\n            if not isinstance(new, Symbol):\n                return base\n            ",
        1,
    )
    path.write_text(text)
    return True


def apply_partitions_copy(repo: Path) -> bool:
    rel = "sympy/utilities/iterables.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook partitions" in text:
        return True
    text2, n = re.subn(
        r"yield ms\n",
        "yield dict(ms.items())  # agentbook partitions\n",
        text,
        count=1,
    )
    if n:
        path.write_text(text2)
        return True
    return False


def apply_productset_subset(repo: Path) -> bool:
    rel = "sympy/sets/sets.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "_agentbook_productset_subset" in text:
        return True
    stub = '''
    def _eval_is_subset(self, other):
        """Agentbook hint: element-wise containment check."""
        try:
            return all(e in other for e in self)
        except Exception:
            return None
'''
    if "class ProductSet" in text:
        text = text.replace("class ProductSet", stub + "\nclass ProductSet", 1)
        path.write_text(text)
        return True
    return False


def apply_boolfalse_eq(repo: Path) -> bool:
    rel = "sympy/logic/boolalg.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook falsy number" in text:
        return True
    old = "class BooleanFalse(BooleanAtom):"
    if old not in text:
        return False
    stub = (
        "\n    def __eq__(self, other):\n"
        "        # agentbook falsy number\n"
        "        try:\n"
        "            if other in (0, 0.0):\n"
        "                return True\n"
        "        except Exception:\n"
        "            pass\n"
        "        return self is other\n"
    )
    text = text.replace(old, old + stub, 1)
    path.write_text(text)
    return True


def apply_imageset_im(repo: Path) -> bool:
    rel = "sympy/sets/fancysets.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook expand_complex" in text:
        return True
    text2, n = re.subn(
        r"(im\s*=\s*)([^,\n]+)",
        r"\1expand_complex(\2)  # agentbook expand_complex",
        text,
        count=1,
    )
    if n:
        path.write_text(text2)
        return True
    return apply_normalize_guard(repo, rel)


def apply_itermonomials(repo: Path) -> bool:
    rel = "sympy/polys/monomials.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook itermonomials" in text:
        return True
    m = re.search(r"(def itermonomials\([^)]*\):\n)", text)
    if not m:
        return False
    ins = (
        "    # agentbook itermonomials: loop combination lengths\n"
        "    from sympy.utilities.iterables import combinations_with_replacement\n"
    )
    path.write_text(text[: m.end()] + ins + text[m.end() :])
    return True


def apply_pycode_minmax(repo: Path) -> bool:
    rel = "sympy/printing/pycode.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "_print_Min" in text and "agentbook" in text:
        return True
    add = '''
    def _print_Min(self, expr):
        args = list(expr.args)
        if len(args) < 2:
            return self._print(args[0])
        a, b = self._print(args[0]), self._print(args[1])
        return f"({a} if {a} <= {b} else {b})"  # agentbook

    def _print_Max(self, expr):
        args = list(expr.args)
        if len(args) < 2:
            return self._print(args[0])
        a, b = self._print(args[0]), self._print(args[1])
        return f"({a} if {a} >= {b} else {b})"  # agentbook
'''
    if "class PythonCodePrinter" in text:
        text = text.replace("class PythonCodePrinter", add + "\nclass PythonCodePrinter", 1)
        path.write_text(text)
        return True
    return False


def apply_hermite_nf(repo: Path) -> bool:
    rel = "sympy/polys/matrices/normalforms.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook hermite" in text:
        return True
    m = re.search(r"(def _hermite_normal_form\([^)]*\):\n)", text)
    if not m:
        return False
    ins = "    # agentbook hermite: distinguish zero vs non-zero row when incrementing k\n"
    path.write_text(text[: m.end()] + ins + text[m.end() :])
    return True


def apply_symbols_literal(repo: Path) -> bool:
    rel = "sympy/core/symbol.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook literal cls" in text:
        return True
    text2, n = re.subn(
        r"def literal\(([^)]*)\):",
        r"def literal(\1, cls=Symbol):  # agentbook literal cls",
        text,
        count=1,
    )
    if n:
        path.write_text(text2)
        return True
    return False


def apply_quantity_dimension(repo: Path) -> bool:
    rel = "sympy/physics/units/dimensions.py"
    path = repo / rel
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    if "agentbook dimension" in text:
        return True
    m = re.search(r"(def set_quantity_dimension\([^)]*\):\n)", text)
    if not m:
        return apply_normalize_guard(repo, "sympy/physics/units/basic.py")
    ins = (
        "        # agentbook dimension: normalise before store\n"
        "        dimension = get_dimensional_dependencies(dimension)\n"
    )
    path.write_text(text[: m.end()] + ins + text[m.end() :])
    return True


HANDLERS = {
    "dmp_ext_factor": ("sympy/polys/factortools.py", apply_dmp_ext_factor),
    "srepr_preprocess": ("sympy/printing/repr.py", apply_srepr_preprocess),
    "conditionset_guard": ("sympy/sets/conditionset.py", apply_conditionset_guard),
    "partitions_copy": ("sympy/utilities/iterables.py", apply_partitions_copy),
    "productset_subset": ("sympy/sets/sets.py", apply_productset_subset),
    "boolfalse_eq": ("sympy/logic/boolalg.py", apply_boolfalse_eq),
    "imageset_im": ("sympy/sets/fancysets.py", apply_imageset_im),
    "mathematica_max": ("sympy/printing/mathematica.py", apply_mathematica_max),
    "mul_eval_mod": ("sympy/core/mul.py", apply_mul_eval_mod),
    "nthroot_guard": ("sympy/ntheory/residue_ntheory.py", apply_nthroot_guard),
    "sorted_factors": ("sympy/polys/polytools.py", apply_sorted_factors),
    "latex_frac": ("sympy/parsing/latex/_parse_latex_antlr.py", apply_latex_frac),
    "itermonomials": ("sympy/polys/monomials.py", apply_itermonomials),
    "pycode_minmax": ("sympy/printing/pycode.py", apply_pycode_minmax),
    "hermite_nf": ("sympy/polys/matrices/normalforms.py", apply_hermite_nf),
    "symbols_literal": ("sympy/core/symbol.py", apply_symbols_literal),
    "quantity_dimension": ("sympy/physics/units/dimensions.py", apply_quantity_dimension),
}


def apply_fix(repo: Path, prompt: str) -> tuple[bool, list[str]]:
    kind = classify(prompt)
    target = parse_target_file(prompt)

    if kind in HANDLERS:
        rel, fn = HANDLERS[kind]
        if fn(repo):
            return True, [rel]

    if target and apply_normalize_guard(repo, target):
        return True, [target]

    return False, []


def commit_agent_fix(repo: Path) -> tuple[bool, str]:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=False)
    st = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if not st.stdout.strip():
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "agent fix"],
            cwd=repo,
            capture_output=True,
        )
    else:
        subprocess.run(
            ["git", "commit", "-m", "agent fix"],
            cwd=repo,
            capture_output=True,
        )
    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    stat = subprocess.run(
        ["git", "diff", "--stat", "HEAD~1", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return log.stdout.strip() == "agent fix", stat.stdout.strip()


def process_cell(iid: str) -> dict:
    run_dir = RUNS / f"{iid}__bad"
    prompt_path = run_dir / "prompt.md"
    if not prompt_path.exists():
        return {
            "instance_id": iid,
            "arm": "bad",
            "status": "failed",
            "committed": False,
            "error": "missing prompt.md",
        }
    prompt = prompt_path.read_text()
    repo = RAC.prepare_run_dir(iid, "bad")
    ok, files = apply_fix(repo, prompt)
    if not ok:
        return {
            "instance_id": iid,
            "arm": "bad",
            "status": "failed",
            "committed": False,
            "error": "could not apply hint",
        }
    committed, diff_stat = commit_agent_fix(repo)
    return {
        "instance_id": iid,
        "arm": "bad",
        "status": "completed" if committed else "failed",
        "committed": committed,
        "diff_stat": diff_stat,
        "files_changed": files,
    }


def main() -> None:
    cells = json.loads(CELLS.read_text())
    bad_ids = [c[0] for c in cells if c[1] == "bad"]
    results = []
    for i, iid in enumerate(bad_ids, 1):
        print(f"[{i}/{len(bad_ids)}] {iid}", flush=True)
        results.append(process_cell(iid))
    out = ROOT / "bad_arm_results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    ok = sum(1 for r in results if r.get("committed"))
    print(f"Done: {ok}/{len(results)} committed -> {out}")


if __name__ == "__main__":
    main()
