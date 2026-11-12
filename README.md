# Sampling conventions for Arctic sea-ice thickness aggregates

Two conventions applied to the same CryoSat-2 record do not give the same ice:
restricting the average to cells observed in at least 90 % of months raises the
mean by 29 cm. That number is not an error in either product — it is the
difference between two estimands, and this repository contains the fields and the
code that make the difference reproducible.

## What is here

    data/MPO_CCI_SIT_25km_v1.0.nc   the derived field set (13.9 MB)
        73 monthly fields on the 432x432 EASE-Grid 2.0:
          population_mask        the cells in each analysis population
          ht_weight_popA/B       inverse-propensity weight per cell
          bias_popA/B            monthly population bias (m), with low/high and
                                 a 0/1 quality flag; Pop-B 2010-10 is flagged
          sea_ice_thickness      the merged product, for reference
    data/mpo_pooled.csv            per-month table produced by the script below
    code/reproduce_mpo.py          recomputes the four pooled estimates
    code/reproduce_from_tables.py  recomputes every other published number
    code/repro_all.py              writes the CSV record of each reviewer correction
    tables/                        the paper's tables as LaTeX

## Run it

    pip install numpy pandas netCDF4 scipy
    python code/reproduce_mpo.py            # four pooled estimates, PASS/FAIL
    python code/reproduce_from_tables.py    # every table-derived number

`reproduce_mpo.py` prints

    [PASS] A_equal         0.605 cm   paper 0.61
    [PASS] B_equal         2.716 cm   paper 2.72
    [PASS] B_equal_noflag  2.519 cm   paper 2.52
    [PASS] B_mass          2.651 cm   paper 2.65

and exits non-zero if any of them moves. The four differ only in how the monthly
values are combined: equal weight over 73 month-fields, equal weight excluding the
flagged month, and weight-mass weighting.

## Provenance

The raw CCI and CS2SMOS monthly fields are distributed by their providers and are
not redistributed here. The netCDF contains only derived quantities: the
observation indicator, the weights and the bias with its interval and flag. The
Airborne IceBird contrast uses the published survey tables.

## Licence and citation

Code MIT; data CC BY 4.0 (see DATA_LICENSE). Cite the article and this repository.
