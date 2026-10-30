"""Controlled failure tests for the v2 pipeline.

Each test copies the Bronze data to a temporary folder, damages the copy in
one specific way, and runs the real pipeline steps on it via BD_AGRI_V2_DIR.
The tests work at two stages:

  Bronze inputs   the BBS district-year table and the Earth Engine extracts
                  are damaged, and the Silver/Gold build (s03) and validation
                  (s03b) are run: these exercise the generic checks (schema,
                  missing values, names, keys, ranges);
  parsed rows     the rows parsed from the yearbook PDFs are damaged, and the
                  BBS step is rerun from them (s01 --from-rows), followed by
                  s03 and s03b: these exercise the checks that use the
                  redundancy of the yearbooks (unit identities, printed
                  national totals, agreement between editions, completeness).

A test passes only if the run stops at the expected step with a diagnostic
that names the expected check and record, and, where the damage breaks a
unit identity, the row is also excluded and logged.  A clean baseline run of
the whole chain (s01 from the parsed rows, s03, s03b) must pass every
validation check and reproduce the real BBS tables and Gold panel exactly.
The real data are never modified.

Run:  python v2/tests/run_failure_tests.py      (or: pytest v2/tests)
Writes v2/outputs/failure_tests/results.csv and one log per test.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[1]
SRC = V2 / "src"
sys.path.insert(0, str(SRC))
from common import panel_sha256  # noqa: E402
OUT = V2 / "outputs" / "failure_tests"
ROWS = "bbs/bbs_boro_rows_all.csv"
STEPS_BRONZE = [["s03_build_panel.py"], ["s03b_validate.py"]]
STEPS_ROWS = [["s01_bbs_extract.py", "--from-rows", "{rows}"], ["s03_build_panel.py"], ["s03b_validate.py"]]
STAGE = {"bronze": "Bronze inputs (s03, s03b)", "rows": "Parsed yearbook rows (s01, s03, s03b)"}


# ── Corruptions of the Bronze inputs (temporary copy only) ──────────────
def unknown_district(b):
    f = b / "bbs" / "bbs_boro_district_year.csv"
    d = pd.read_csv(f)
    i = d.index[(d.district == "Sunamganj") & (d.harvest_year == 2017)][0]
    d.loc[i, "district"] = "Sunamgonjj"
    d.to_csv(f, index=False)


def missing_column(b):
    f = b / "gee" / "ndvi_all.csv"
    pd.read_csv(f).drop(columns="ndvi_peak").to_csv(f, index=False)


def duplicate_key(b):
    f = b / "bbs" / "bbs_boro_district_year.csv"
    d = pd.read_csv(f)
    row = d[(d.district == "Sylhet") & (d.harvest_year == 2020)]
    pd.concat([d, row]).to_csv(f, index=False)


def invalid_value(b):
    f = b / "gee" / "ndvi_all.csv"
    d = pd.read_csv(f)
    d.loc[(d.district == "Rajshahi") & (d.harvest_year == 2019), "ndvi_peak"] = 1.7
    d.to_csv(f, index=False)


def wrong_type(b):
    f = b / "bbs" / "bbs_boro_district_year.csv"
    d = pd.read_csv(f).astype({"yield_t_ha": object})
    d.loc[(d.district == "Dhaka") & (d.harvest_year == 2018), "yield_t_ha"] = "n/a"
    d.to_csv(f, index=False)


def missing_value(b):
    f = b / "bbs" / "bbs_boro_district_year.csv"
    d = pd.read_csv(f)
    d.loc[(d.district == "Bogura") & (d.harvest_year == 2021), "yield_t_ha"] = None
    d.to_csv(f, index=False)


# ── Corruptions of the parsed yearbook rows (temporary copy only) ────────
def _row(d, district, crop_year, edition):
    return d.index[(d.district == district) & (d.crop_year == crop_year) & (d.book_year == edition)][0]


def transposed_digits(b):
    d = pd.read_csv(b / ROWS)
    i = _row(d, "Rajshahi", "2019-20", 2021)
    s = str(int(d.loc[i, "production_t"]))
    d.loc[i, "production_t"] = float(s[0] + s[2] + s[1] + s[3:])        # 254667 -> 245667
    d.to_csv(b / ROWS, index=False)


def swapped_rows(b):
    d = pd.read_csv(b / ROWS)
    for cy in ["2019-20", "2020-21"]:                                    # both crop years of the printed lines
        i, j = _row(d, "Dhaka", cy, 2021), _row(d, "Bogura", cy, 2021)
        d.loc[[i, j], "raw_name"] = d.loc[[j, i], "raw_name"].values
    d.to_csv(b / ROWS, index=False)


def dropped_row(b):
    d = pd.read_csv(b / ROWS)
    d.drop(index=_row(d, "Khulna", "2024-25", 2025)).to_csv(b / ROWS, index=False)


def misaligned_cell(b):
    d = pd.read_csv(b / ROWS)
    i = _row(d, "Bogura", "2019-20", 2021)
    d.loc[i, "yield_t_ha"] = d.loc[i, "yield_maund_acre"]                # yield read from the maund/acre column
    d.to_csv(b / ROWS, index=False)


CASES = [
    # name, stage, corruption, description, expected failing step, check named in the expectation,
    # substrings the diagnostic must contain, row that must be excluded by the unit identities
    ("unknown_district", "bronze", unknown_district, "BBS district 'Sunamganj' (2017) renamed to unknown 'Sunamgonjj'",
     "s03_build_panel.py", "[DISTRICT]", ["[DISTRICT]", "bbs", "Sunamgonjj 2017"], None),
    ("missing_column", "bronze", missing_column, "required column ndvi_peak removed from gee/ndvi_all.csv",
     "s03_build_panel.py", "[SCHEMA]", ["[SCHEMA]", "ndvi_all.csv", "ndvi_peak"], None),
    ("duplicate_key", "bronze", duplicate_key, "BBS record Sylhet 2020 duplicated",
     "s03_build_panel.py", "[KEY]", ["[KEY]", "bbs_boro", "Sylhet", "2020"], None),
    ("invalid_value", "bronze", invalid_value, "NDVI for Rajshahi 2019 set to 1.7 (valid range 0–1)",
     "s03_build_panel.py", "[RANGE]", ["[RANGE]", "ndvi_peak", "Rajshahi 2019", "1.7"], None),
    ("wrong_type", "bronze", wrong_type, "BBS yield for Dhaka 2018 replaced by the text 'n/a'",
     "s03_build_panel.py", "[SCHEMA]", ["[SCHEMA]", "bbs_boro_district_year.csv", "yield_t_ha", "Dhaka 2018", "n/a"],
     None),
    ("missing_value", "bronze", missing_value, "BBS yield for Bogura 2021 left empty",
     "s03_build_panel.py", "[MISSING]", ["[MISSING]", "yield_t_ha", "Bogura 2021"], None),
    ("transposed_digits", "rows", transposed_digits,
     "two digits of Rajshahi's 2019-20 production transposed in the 2021 edition (254,667 → 245,667 t)",
     "s03b_validate.py", "national-total check", ["printed national total", "2021 edition, 2019-20"],
     ("Rajshahi", "2019-20", 2021)),
    ("swapped_rows", "rows", swapped_rows,
     "the printed lines of Dhaka and Bogura exchanged in the 2021 edition (both crop years)",
     "s03b_validate.py", "edition-agreement check", ["two editions agree", "Bogura 2019-20", "Dhaka 2019-20"], None),
    ("dropped_row", "rows", dropped_row,
     "Khulna's 2024-25 row removed from the 2025 edition, the only edition that prints that crop year",
     "s03_build_panel.py", "[MISSING]", ["[MISSING]", "fact_boro_panel", "Khulna 2025"], None),
    ("misaligned_cell", "rows", misaligned_cell,
     "Bogura's 2019-20 yield in the 2021 edition read from the maund-per-acre column (3.882 → 42.08)",
     "s03b_validate.py", "edition-agreement check", ["two editions agree", "Bogura 2019-20"],
     ("Bogura", "2019-20", 2021)),
]


def workspace():
    tmp = Path(tempfile.mkdtemp(prefix="bdagri_test_"))
    shutil.copytree(V2 / "data" / "bronze", tmp / "data" / "bronze")
    return tmp


def run_pipeline(tmp, steps):
    env = dict(os.environ, BD_AGRI_V2_DIR=str(tmp), PYTHONIOENCODING="utf-8")
    rows = str(tmp / "data" / "bronze" / ROWS)
    log, failed = [], None
    for step in steps:
        args = [a.replace("{rows}", rows) for a in step]
        p = subprocess.run([sys.executable, "-W", "ignore", *args], cwd=SRC, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        log.append(f"$ python {' '.join(step)}  (exit {p.returncode})\n{p.stdout}{p.stderr}")
        if p.returncode:
            failed = step[0]
            break
    return failed, "\n".join(log)


def diagnostic(log, tmp):
    """The error message of a stopped step: the DataContractError, or the
    failed checks of the validation report."""
    lines = [l for l in log.splitlines() if "DataContractError" in l]
    if lines:
        return lines[-1].split("DataContractError: ")[-1]
    report = tmp / "outputs" / "validation_report.csv"
    if "validation failed" in log and report.exists():
        rep = pd.read_csv(report)
        return "; ".join(f"{r.check}: {r.observed}" for r in rep[rep.status == "FAIL"].itertuples())
    return ""


def panel_hash(db):
    return panel_sha256(db)


def excluded(tmp, row):
    f = tmp / "data" / "bronze" / "bbs" / "bbs_qc_failures.csv"
    if row is None or not f.exists():
        return False
    q = pd.read_csv(f)
    return bool(((q.district == row[0]) & (q.crop_year == row[1]) & (q.book_year == row[2])).any())


def run_case(name, stage, corrupt, desc, step, check_label, expect, exclude):
    tmp = workspace()
    try:
        corrupt(tmp / "data" / "bronze")
        failed, log = run_pipeline(tmp, STEPS_BRONZE if stage == "bronze" else STEPS_ROWS)
        diag = diagnostic(log, tmp)
        was_excluded = excluded(tmp, exclude)
        ok = failed == step and all(s in diag for s in expect) and (exclude is None or was_excluded)
        short = step.split("_")[0]
        observed = f"stopped at {short}" if failed else "completed"
        if exclude is not None:
            observed += "; row excluded by the unit identities" if was_excluded else "; row NOT excluded"
        return dict(test=name, stage=STAGE[stage], corruption=desc,
                    expected=f"stop at {short}, {check_label}"
                             + ("; row excluded by the unit identities" if exclude else ""),
                    observed=observed, diagnostic=diag, result="PASS" if ok else "FAIL"), log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def run_clean():
    """Baseline: the whole chain from the unmodified parsed rows."""
    tmp = workspace()
    try:
        failed, log = run_pipeline(tmp, STEPS_ROWS)
        rep = pd.read_csv(tmp / "outputs" / "validation_report.csv") if not failed else pd.DataFrame()
        n_fail = int((rep.status == "FAIL").sum()) if len(rep) else -1
        bbs = "bbs/bbs_boro_district_year.csv"
        same_bbs = not failed and sha(tmp / "data" / "bronze" / bbs) == sha(V2 / "data" / "bronze" / bbs)
        h_tmp = panel_hash(tmp / "data" / "gold" / "bangladesh_agri_v2.duckdb") if not failed else ""
        h_real = panel_hash(V2 / "data" / "gold" / "bangladesh_agri_v2.duckdb")
        ok = failed is None and n_fail == 0 and same_bbs and h_tmp == h_real
        return dict(test="clean_rerun", stage=STAGE["rows"], corruption="none (unmodified copy)",
                    expected="all steps complete, 0 FAIL checks, BBS table and Gold panel identical to the real ones",
                    observed=(f"completed; {len(rep)} checks, {n_fail} FAIL; BBS table "
                              f"{'identical' if same_bbs else 'differs'}; panel SHA-256 "
                              f"{'matches' if h_tmp == h_real else 'differs'} ({h_tmp[:12]})")
                    if not failed else f"stopped at {failed}",
                    diagnostic="", result="PASS" if ok else "FAIL"), log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in CASES:
        row, log = run_case(*case)
        (OUT / f"{case[0]}.log").write_text(log, encoding="utf-8")
        rows.append(row)
        print(f"{row['result']}  {row['test']}: {row['diagnostic'][:110]}", flush=True)
    row, log = run_clean()
    (OUT / "clean_rerun.log").write_text(log, encoding="utf-8")
    rows.append(row)
    print(f"{row['result']}  clean_rerun: {row['observed']}", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "results.csv", index=False)
    if any(r["result"] != "PASS" for r in rows):
        sys.exit("one or more failure tests did not behave as expected")


# pytest entry points
def test_failure_cases():
    for case in CASES:
        assert run_case(*case)[0]["result"] == "PASS", case[0]


def test_clean_rerun():
    assert run_clean()[0]["result"] == "PASS"


if __name__ == "__main__":
    main()
