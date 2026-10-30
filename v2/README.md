# Bangladesh Boro rice: an open, validated data engineering pipeline

This folder contains a Bronze–Silver–Gold pipeline (Python + DuckDB) that
builds a district-level panel of Boro rice statistics for all 64 districts of
Bangladesh, harvest years 2011–2025, using **only values printed in the BBS
Yearbook of Agricultural Statistics** (no proxy, interpolated or imputed
values), aligned with satellite, flood and climate data.

## What the pipeline does

| Component | Description |
|---|---|
| BBS statistics | District "Total Boro" tables extracted from all 14 yearbook editions (2012–2025); 64 districts × 15 seasons (960 rows), each with its edition and page |
| Crop calendar | Every row keyed on **harvest year** (BBS crop year 2012-13 → 2013) |
| NDVI | MODIS MOD13Q1 v061, peak season (Jan–Apr), cropland pixels only (ESA WorldCover), QA-filtered |
| Climate | ERA5-Land daily: season (Nov–May) mean temperature, mean daily maximum, precipitation; hot days > 35 °C (Mar–May) |
| Flood | Monsoon flood (Jun–Oct of t−1) and flash flood (Apr–May of t), net of same-year dry-season water, from JRC monthly (Landsat) and Sentinel-1 SAR, kept as separate series |
| Demonstration | Vulnerability index with weight sensitivity, global Moran's I and LISA (FDR-corrected) |

## Data model and validation

* `src/schema.py` is the single specification of every Gold table (grain,
  key, columns, types, units, sources), each source's product availability
  versus the period used, and the plausible value ranges.
* `docs/data_dictionary.md` is generated from it.
* `mappings/district_crosswalk.csv` lists every district spelling found in
  the BBS yearbooks, GADM and the Earth Engine extracts, the canonical
  district and GADM identifier it maps to, and the rule used.
* Unrecognised district names stop the pipeline; they are never dropped or
  assigned silently. Earth Engine extracts that lack an expected variable are
  re-extracted rather than reused from cache.

## Failure tests

```bash
python v2/tests/run_failure_tests.py
```

Copies the data to a temporary folder, damages the copy in one way per test
and runs the real pipeline steps on it. Six tests damage the Bronze inputs of
the Silver/Gold build (unknown district name, missing column, duplicate
district-year, value out of range, text in a numeric column, empty BBS
value). Four damage the rows parsed from the yearbook PDFs (transposed
digits, two districts' lines exchanged, a dropped row, a yield read from the
wrong column); for these the BBS step is rerun from the damaged rows
(`s01_bbs_extract.py --from-rows`), so the unit identities, national totals,
edition comparison and panel completeness are exercised. Each test passes only if the run stops
at the expected step with a diagnostic naming the check and the record (and,
where a unit identity breaks, the row is excluded and logged). A clean
baseline run of the whole chain must pass every check and reproduce the real
BBS table and Gold panel exactly. The real data are never modified. Results:
`outputs/failure_tests/results.csv` and one log per test.

## Data checks performed

* Crop years are read from each table header; a row whose crop-year blocks
  do not match the header, or a district printed twice in one table, stops
  the extraction (nothing is assigned by position or dropped).
* Each BBS row passes three arithmetic identities (acres↔hectares,
  maund/acre↔t/ha, area × yield = production); rows failing are excluded.
* District sums equal the printed national total in every edition where the
  national row is printed (`data/bronze/bbs/bbs_edition_checks.csv`).
* Years printed in two editions agree (differences ≤ 1 ha, rounding);
  the later edition is used (`bbs_edition_diffs.csv`).
* Range validation and duplicate checks on every Silver table (the
  pipeline stops on any failure; a log is written to `logs/` locally).

## Setup

All commands are run from the repository root.

1. **Python.** Python 3.11 or later (results were produced with 3.13.7 on
   Windows 11). Create an environment and install the dependencies:

   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install -r v2/requirements-lock.txt   # Windows
   # .venv/bin/python -m pip install -r v2/requirements-lock.txt     # Linux/macOS
   ```

   `requirements-lock.txt` pins every package, direct and indirect, to the
   version that produced the results. `requirements.txt` pins only the direct
   dependencies; installing from it gives newer indirect packages, which
   produced the same outputs in the fresh-setup test below.

2. **BBS yearbooks (not redistributed).** Download the Yearbook of
   Agricultural Statistics, 2012–2025 editions, from bbs.gov.bd and save them
   as `data/bronze/bbs/pdfs/bbs_agri_yearbook_<edition>.pdf` (e.g.
   `bbs_agri_yearbook_2025.pdf`). `v2/data/bronze/manifest.csv` lists the
   SHA-256 of each file used. The pipeline rewrites the manifest on every run,
   so after a run `git diff v2/data/bronze/manifest.csv` is empty if your
   files are the ones used, and shows the rows of any file that differs.

3. **GADM boundaries (licence does not permit redistribution).** Download the
   GADM v4.1 Bangladesh shapefile (`gadm41_BGD_shp.zip`) from gadm.org and
   unzip it into `data/bronze/gadm_shapefiles/` (the pipeline reads
   `gadm41_BGD_2.shp` and `gadm41_BGD_0.shp`).

4. **Optional: Google Earth Engine.** Only needed to re-extract satellite and
   climate data; the extracts used for the results are included in
   `v2/data/bronze/gee/`. To re-extract, run `earthengine authenticate` with an
   account that can use project `bd-agri-climate` (or change `GEE_PROJECT` in
   `src/common.py`) and delete the extracts you want to recompute. The
   date each extract was computed is kept in
   `v2/data/bronze/gee/extraction_dates.json` and copied into the manifest.

5. **Optional: pandoc.** Only needed to rebuild the manuscript; without it the
   pipeline skips that step. Figure 7 (`outputs/figures/fig7_dashboard.png`)
   is a screenshot of the dashboard kept in the repository; it is the only
   figure the pipeline does not regenerate.

## Run

```bash
python v2/run_all.py
python v2/tests/run_failure_tests.py
python v2/src/s06_manuscript.py paper_ems
```

The manuscript quotes the failure-test and fresh-setup results, so it is
rebuilt after the tests. It reads them only if they were produced from the
current Gold panel (checked by SHA-256); otherwise it is marked as a draft
with the reason at the top.

| Step | Script | Output |
|---|---|---|
| 1 | `s01_bbs_extract.py` | `data/bronze/bbs/*.csv` |
| 2 | `s02_gee_extract.py` | `data/bronze/gee/*.csv` (uses the cache; contacts Earth Engine only for missing or incomplete extracts) |
| 2b | `s02b_manifest.py` | `data/bronze/manifest.csv`: product, version, date windows, parameters and SHA-256 of every source file and extract |
| 3 | `s03_build_panel.py` | `data/silver/*.parquet`, `data/gold/bangladesh_agri_v2.duckdb` |
| 3b | `s03b_validate.py` | `outputs/validation_report.csv` (stops the run on any FAIL), `mappings/district_crosswalk.csv`, `docs/data_dictionary.md` |
| 4 | `s04_analysis.py` | `outputs/tables/*.csv`, `outputs/results.json` |
| 5 | `s05_figures.py` | `outputs/figures/*.png`, including the lineage diagram `fig8_lineage.png` |
| 6 | `s06_manuscript.py paper_ems` | the Environmental Modelling & Software manuscript (`paper_ems/`) |

`run_all.py` also writes `outputs/pipeline_timings.json`. The reference list
is built from `paper_ems/references.json`, generated from Crossref and
DataCite by `src/fetch_references.py`.

On Windows, the PDF step may print `Exception ignored in atexit callback ...
PermissionError` when camelot cannot delete its temporary page files. The
message comes from camelot's clean-up after the step has finished and does not
affect any output.

## Notebooks

* `notebooks/01_Data_Engineering_Pipeline.ipynb` builds the whole dataset from
  the original sources, step by step, with the documentation as markdown:
  GADM boundaries, the BBS table extraction and its checks, the Earth Engine
  extraction (NDVI, ERA5-Land, JRC, Sentinel-1), the manifest, the Silver and
  Gold layers, and the full validation report. Its last section confirms that
  every file and table it builds is identical to the output of `run_all.py`.
  It writes to `notebooks/build/` and takes about 4 minutes when it reuses the
  Earth Engine extracts in the repository; set `REUSE_REPOSITORY_EXTRACTS =
  False` to compute every extract from Earth Engine (about 75 minutes).
* `notebooks/02_Evaluation_and_Outputs.ipynb` documents the outputs and the
  evaluation (validation report, failure tests, reproducibility, run time,
  flood consistency, example application). It only reads the outputs, so it
  runs in under a minute without the yearbook PDFs or Earth Engine.

Jupyter is not among the pinned packages:

```bash
python -m pip install jupyterlab
jupyter lab v2/notebooks
```

## Checking a fresh setup

```bash
python v2/tests/run_fresh_setup_test.py
```

Builds a clean copy holding only repository files and the documented
downloads (no generated file), creates two new virtual environments (from
`requirements.txt` and from `requirements-lock.txt`), and in each runs the
pipeline, the failure tests and the manuscript build, then compares every
output with this checkout. Takes about 15 minutes per environment. Results:
`docs/fresh_setup_summary.json` and `docs/fresh_setup_comparison_<env>.csv`.

The comparison alone can be run on any two output folders:

```bash
python v2/tests/compare_outputs.py <reference v2 folder> <new v2 folder> comparison.csv
```

Every file falls in exactly one class: `identical` (bytes match), `same
content` (the format stores write times or folder paths: DuckDB tables are
compared value by value, Word files part by part, logs without the folder
path), `run time only` (only measured run times differ: the timing record
and the manuscript), `kept in repository` (the dashboard screenshot and a
one-off Sentinel-1 check record, which are not generated) or `DIFFERENT`
(anything else, or a missing file; the script then exits with status 1).
The documented test is in `docs/fresh_setup_test.md`.

Dashboard: `streamlit run v2/dashboard_v2.py`
