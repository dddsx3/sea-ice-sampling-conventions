# -*- coding: utf-8 -*-
"""Recompute the three pooled bias estimates from the released product file.

The paper quotes +0.61 cm (Pop-A), and +2.72 / +2.52 / +2.65 cm for Pop-B. Those
were the three numbers the earlier version could not support, because the weights
and the per-month biases lived only in the authors' working tree. They now ship
in `data/MPO_CCI_SIT_25km_v1.0.nc`, which holds, per month and per population:

    bias_pop{A,B}          inverse-propensity-weighted mean bias (m)
    bias_lo/hi_pop{A,B}    its interval
    bias_quality_pop{A,B}  0 = usable, 1 = flagged (Pop-B 2010-10)
    ht_weight_pop{A,B}     per-cell inverse-propensity weight

Nothing here re-fits a model. The three estimates differ only in how the monthly
values are combined, which is the point the paper makes:

    +2.72  equal weight over the 73 month-fields
    +2.52  equal weight excluding the flagged month (2010-10)
    +2.65  weight-mass weighting over the 73 month-fields

Run from the paper root:  python code/reproduce_mpo.py
Writes data/mpo_pooled.csv and exits non-zero if a value misses its target.
"""
import datetime as dt
import os
import sys

import numpy as np
from netCDF4 import Dataset

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NC = os.path.join(ROOT, "data", "MPO_CCI_SIT_25km_v1.0.nc")
OUT = os.path.join(ROOT, "data", "mpo_pooled.csv")

TARGETS = {"A_equal": 0.61, "B_equal": 2.72, "B_equal_noflag": 2.52, "B_mass": 2.65}


def months(nc):
    t = np.array(nc["time"][:])
    return np.array([(dt.date(1970, 1, 1) + dt.timedelta(days=int(x))).strftime("%Y-%m")
                     for x in t])


def weight_mass(nc, pop):
    w = np.array(nc["ht_weight_pop" + pop][:], dtype="float64")
    ok = (w > 0) & (w < 50) & np.isfinite(w)
    return np.array([np.nansum(w[i][ok[i]]) for i in range(w.shape[0])]), ok.sum(axis=(1, 2))


def main():
    nc = Dataset(NC)
    m = months(nc)
    rows, res = [], {}
    for pop in ("A", "B"):
        b = np.array(nc["bias_pop" + pop][:], dtype="float64")
        q = np.array(nc["bias_quality_pop" + pop][:])
        W, ncell = weight_mass(nc, pop)
        ok = np.isfinite(b) & (W > 0)
        res[pop + "_equal"] = float(np.mean(b[ok]) * 100)
        if pop == "B":
            keep = ok & (q == 0)
            res["B_equal_noflag"] = float(np.mean(b[keep]) * 100)
            res["B_mass"] = float(np.sum(W[ok] * b[ok]) / np.sum(W[ok]) * 100)
        for i in range(len(m)):
            rows.append(dict(month=m[i], population="Pop-" + pop, bias_m=b[i],
                             quality=int(q[i]), weight_mass=W[i], n_weighted_cells=int(ncell[i])))
    nc.close()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("month,population,bias_m,quality,weight_mass,n_weighted_cells\n")
        for r in rows:
            fh.write("%s,%s,%.9g,%d,%.9g,%d\n" % (r["month"], r["population"], r["bias_m"],
                                                  r["quality"], r["weight_mass"], r["n_weighted_cells"]))

    bad = 0
    for k, target in TARGETS.items():
        got = res[k]
        ok = abs(got - target) <= 0.005
        bad += 0 if ok else 1
        print("[%s] %-16s %6.3f cm   paper %5.2f" % ("PASS" if ok else "FAIL", k, got, target))
    print("\n73 month-fields, 1 flagged (Pop-B 2010-10); per-month table written to %s"
          % os.path.relpath(OUT, ROOT))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
