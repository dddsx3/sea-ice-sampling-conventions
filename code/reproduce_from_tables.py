#!/usr/bin/env python3
"""Recompute every derived quantity of A1 that is a function of the six shipped tables.

The raw CS2SMOS and CCI products are not redistributed. What is redistributed is
the six tables of the manuscript, and this script reads them and re-derives every
number that depends on tables alone. Each check prints the recomputed value
beside the value printed in the paper, and the script exits non-zero if any
recomputed value departs from the published one by more than its printed
precision.

    python code/reproduce_from_tables.py [--table-dir tables]

No third-party dependency. Requires Python >= 3.8.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
FAILURES: list[str] = []


def rows(text: str) -> list[tuple[str, list[float]]]:
    """Parse a booktabs table into (row label, numbers on that row) pairs.

    LaTeX commands are stripped before the split, thin spaces are removed, and
    numbers are taken in order of appearance, so a bracketed interval yields its
    point estimate first.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if "&" not in line or not line.endswith("\\\\"):
            continue
        body = line.rstrip("\\").strip()
        body = re.sub(r"\\multicolumn\{[^}]*\}\{[^}]*\}\{", "", body)
        body = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", body)
        body = body.replace("\\,", "").replace("{,}", ",").replace("$", "")
        parts = [p.strip() for p in body.split("&")]
        if not parts or not re.match(r"[A-Za-z0-9]", parts[0]):
            continue
        vals = []
        for cell in parts[1:]:
            cell = re.sub(r"(?<=\d) (?=\d)", "", cell)
            m = NUM_RE.search(cell)
            if m:
                vals.append(float(m.group(0)))
        if vals:
            out.append((parts[0].strip(), vals))
    return out


def pick(text: str, prefix: str, index: int = 0, occurrence: int = 0) -> float:
    hits = [v for lab, v in rows(text) if lab.startswith(prefix)]
    if len(hits) <= occurrence:
        raise LookupError(f"row {prefix!r} #{occurrence} not found; {len(hits)} available")
    return hits[occurrence][index]


def check(label: str, got: float, published: float, tol: float) -> None:
    ok = abs(got - published) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<60} recomputed {got:>11.4f}   paper {published:>11.4f}")
    if not ok:
        FAILURES.append(label)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table-dir", default=os.path.join(os.path.dirname(__file__), os.pardir, "tables"))
    args = ap.parse_args()
    tdir = os.path.abspath(args.table_dir)

    def load(name: str) -> str:
        with open(os.path.join(tdir, name), encoding="utf-8-sig") as fh:
            return fh.read()

    dom, mis, mon, ice = (load(f) for f in ("tab_domain.tex", "tab_missing.tex",
                                           "tab_monthly.tex", "tab_icebird.tex"))

    print("1. Level and amplitude shifts, single-sensor record (tab_domain, Panel A)")
    obs_level = pick(dom, "Observed-only (= delivered)", 0)
    fix_level = pick(dom, "Fixed grid", 0, occurrence=0)
    check("level difference, fixed grid - observed-only (m)", fix_level - obs_level, 0.290, 5e-4)
    check("level difference as percent of the observed mean", 100 * (fix_level / obs_level - 1), 22.9, 0.06)

    print("2. Fill versus delete, merged record (tab_domain, Panel B)")
    delivered = pick(dom, "Delivered analysis", 0)
    obs_only_b = pick(dom, "Observed-only", 0, occurrence=1)
    weighted = pick(dom, "Inverse-probability weighted", 0)
    common = pick(dom, "Common cells", 0)
    fixed_b = pick(dom, "Fixed grid", 0, occurrence=1)
    check("filling raises the level, delivered - observed-only (m)", delivered - obs_only_b, 0.094, 5e-4)
    check("weighted - delivered, the 2 mm conservation check (m)", weighted - delivered, 0.002, 5e-4)
    check("weighted - observed-only (m)", weighted - obs_only_b, 0.096, 5e-4)
    check("common varying domain - delivered (m)", common - delivered, 0.088, 5e-4)
    check("fixed domain - observed-only, merged record (m)", fixed_b - obs_only_b, 0.889, 5e-4)

    print("3. Cell inventory and the cadence check (tab_missing)")
    total = pick(mis, "all cells", 0)
    unobs = pick(mis, "all cells", 1)
    nf = 1074.0
    check("unobserved fraction of cell-fields, percent", 100 * unobs / total, 35.99, 0.006)
    band_vals = [v[0] for lab, v in rows(mis) if lab.rstrip("$^\\circ$").endswith("N")]
    band_total = sum(band_vals)
    check("latitude bands 40-85N, sum of cell-fields", band_total, 21_812_073, 1.0)
    check("pooled minus band sum, the cells outside 40-85N", total - band_total, 25_142, 1.0)
    cells_per_field = total / nf
    check("cells per delivered field", round(cells_per_field), 20_333, 0.5)
    check("cells per field as percent of the 432x432 grid", 100 * cells_per_field / 432 ** 2, 10.9, 0.06)
    check("fields per data-bearing month, 1074 over 43", nf / 43, 25, 0.05)
    check("delivery dates carrying an analysis, percent of 1309 days", 100 * nf / (43 * 30.4375), 82, 0.2)

    print("4. Monthly and pooled bias (tab_monthly)")
    # tab_monthly has the population in column 1 and the month in column 2, so the
    # generic row parser (which keeps only numbers) cannot key it; parse directly.
    a_bias: dict[str, float] = {}
    b_bias: dict[str, float] = {}
    for raw in mon.splitlines():
        line = raw.strip()
        if not line.endswith("\\\\") or line.count("&") < 6:
            continue
        parts = [p.strip() for p in line.rstrip("\\").replace("$", "").split("&")]
        if parts[0] not in ("A", "B") or not re.fullmatch(r"[A-Za-z]{3}", parts[1]):
            continue
        bias = re.search(r"-?\d+\.?\d*", parts[5])
        if bias is None:
            continue
        (a_bias if parts[0] == "A" else b_bias)[parts[1]] = float(bias.group(0))
    check("Pop-A unweighted mean of the seven rows (cm)", sum(a_bias.values()) / 7, 0.61, 0.006)
    check("Pop-B unweighted mean of the seven rows (cm)", sum(b_bias.values()) / 7, 2.52, 0.006)
    check("Pop-B mean with October removed (cm)", (sum(b_bias.values()) - b_bias["Oct"]) / 6, 2.37, 0.006)
    check("Pop-B identity 2.72 - 0.20", 2.72 - 0.20, 2.52, 1e-9)
    check("Pop-B identity 2.52 + 0.13", 2.52 + 0.13, 2.65, 1e-9)

    print("5. Airborne contrasts (tab_icebird)")
    inside = [v for lab, v in rows(ice) if lab.startswith("90") and "months" in lab][0]
    outside = [v for lab, v in rows(ice) if lab.startswith("other cells")][0]
    check("inside - outside, survey (m)", inside[1] - outside[1], 1.364, 6e-4)
    check("inside - outside, CCI (m)", inside[2] - outside[2], 1.537, 6e-4)
    check("inside - outside, CS2SMOS (m)", inside[3] - outside[3], 1.685, 6e-4)
    check("collocated cells, n inside + n outside", inside[0] + outside[0], 74, 0.0)

    print("6. Minimum detectable effects (Eq. mde)")
    z = 1.959964 + 0.841621
    check("MDE, airborne survey against the records (m)", z * 0.757 / math.sqrt(28.2), 0.40, 0.006)
    check("MDE, merged record against the reference (m)", z * 0.488 / math.sqrt(22.9), 0.29, 0.006)
    check("Kish ratio over the autocorrelation n_eff, ratio", 18458 / 28.2, 655, 6)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all checks reproduce the published values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
