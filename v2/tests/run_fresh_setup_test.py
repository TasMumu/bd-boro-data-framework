"""Fresh-setup reproducibility test.

    python v2/tests/run_fresh_setup_test.py [--workdir DIR] [--keep]

Builds a clean copy of the repository holding only what a clone contains
(code, tests, cached Earth Engine extracts, manuscript sources and the two
files kept in the repository rather than generated), plus the external inputs
the README asks users to download (the BBS yearbook PDFs and GADM shapefiles,
copied from this checkout). No generated file is copied.

For each requirements file it then creates a new virtual environment,
installs the file, and in a fresh copy runs run_all.py, the failure tests and
the manuscript build, and compares every output with this checkout
(compare_outputs.py).

Writes docs/fresh_setup_summary.json and docs/fresh_setup_comparison_<env>.csv.
Takes about 15 minutes per environment, mostly package installation.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from compare_outputs import RECORDED
from run_failure_tests import panel_hash

V2 = Path(__file__).resolve().parents[1]
ROOT = V2.parent
DOCS = V2 / "docs"
ENVS = {"A": "requirements.txt", "B": "requirements-lock.txt"}
REPO = ["v2/src", "v2/tests", "v2/run_all.py", "v2/requirements.txt", "v2/requirements-lock.txt",
        "v2/README.md", "v2/dashboard_v2.py", "v2/paper_ems/parts", "v2/paper_ems/highlights.md",
        "v2/paper_ems/references.json", "v2/data/bronze/gee/extraction_times.json",
        "v2/data/bronze/gee/extraction_dates.json", "CITATION.cff",
        # results of the previous fresh-setup test, which the manuscript quotes
        "v2/docs/fresh_setup_summary.json", "v2/docs/fresh_setup_comparison_A.csv",
        "v2/docs/fresh_setup_comparison_B.csv", "v2/docs/notebook_rebuild_summary.json",
        *(f"v2/{r}" for r in RECORDED)]
DOWNLOADS = [("data/bronze/bbs/pdfs", "bbs_agri_yearbook_20*.pdf"),
             ("data/bronze/gadm_shapefiles", "gadm41_BGD_[02].*")]


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    elif src.exists():
        shutil.copy2(src, dst)


def build_tree(tree):
    shutil.rmtree(tree, ignore_errors=True)
    for rel in REPO:
        copy(ROOT / rel, tree / rel)
    for f in (V2 / "data" / "bronze" / "gee").glob("*_20*.csv"):
        copy(f, tree / "v2" / "data" / "bronze" / "gee" / f.name)
    for folder, pattern in DOWNLOADS:
        for f in (ROOT / folder).glob(pattern):
            copy(f, tree / folder / f.name)


def venv_python(venv):
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd, log, cwd=None):
    t0 = time.time()
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n$ {' '.join(map(str, cmd))}\n")
        fh.flush()
        p = subprocess.run(list(map(str, cmd)), cwd=cwd, stdout=fh, stderr=subprocess.STDOUT,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return p.returncode, round(time.time() - t0)


def pins(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        line = line.split("#")[0].strip()
        if "==" in line:
            k, v = line.split("==", 1)
            out[k.strip().lower().replace("_", "-").replace(".", "-")] = v.strip()
    return out


def test_env(name, req, work, ref_hash):
    log = work / f"env_{name}.log"
    log.unlink(missing_ok=True)
    venv = work / f"venv_{name}"
    shutil.rmtree(venv, ignore_errors=True)
    py = venv_python(venv)
    r = dict(requirements=req)
    run([sys.executable, "-m", "venv", venv], log)
    run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"], log)
    r["install_exit"], r["install_s"] = run([py, "-m", "pip", "install", "-r", V2 / req], log)
    r["pip_check_ok"] = run([py, "-m", "pip", "check"], log)[0] == 0
    freeze = work / f"freeze_{name}.txt"
    freeze.write_text(subprocess.run([str(py), "-m", "pip", "freeze"], capture_output=True, text=True).stdout)
    got, lock = pins(freeze), pins(V2 / "requirements-lock.txt")
    r["packages"] = len(got)
    r["packages_differing_from_lock"] = sorted(f"{k} {lock.get(k, '-')} -> {v}" for k, v in got.items()
                                               if lock.get(k) != v)
    r["python"] = subprocess.run([str(py), "-c", "import platform; print(platform.python_version())"],
                                 capture_output=True, text=True).stdout.strip()

    tree = work / "repo"
    build_tree(tree)
    tv2 = tree / "v2"
    r["run_all_exit"], r["run_all_s"] = run([py, "v2/run_all.py"], log, cwd=tree)
    r["failure_tests_exit"], r["failure_tests_s"] = run([py, "v2/tests/run_failure_tests.py"], log, cwd=tree)
    # Rebuild the manuscript now that the failure-test results exist (as in the README)
    r["manuscript_exit"] = run([py, "s06_manuscript.py", "paper_ems"], log, cwd=tv2 / "src")[0]
    ft = pd.read_csv(tv2 / "outputs" / "failure_tests" / "results.csv")
    cases = ft[ft.test != "clean_rerun"]
    r["failure_cases_passed"] = f"{int((cases.result == 'PASS').sum())} of {len(cases)}"
    r["baseline"] = " ".join(ft[ft.test == "clean_rerun"].result) or "not run"
    r["validation"] = json.loads((tv2 / "outputs" / "validation_summary.json").read_text())["by_status"]
    r["panel_sha256_matches"] = panel_hash(tv2 / "data" / "gold" / "bangladesh_agri_v2.duckdb") == ref_hash
    out = DOCS / f"fresh_setup_comparison_{name}.csv"
    r["compare_exit"] = run([sys.executable, "-W", "ignore", V2 / "tests" / "compare_outputs.py", V2, tv2, out],
                            log)[0]
    c = pd.read_csv(out)
    r["files_compared"] = len(c)
    r["comparison"] = c.status.value_counts().to_dict()
    r["different"] = c[c.status == "DIFFERENT"].file.tolist()
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path(tempfile.gettempdir()) / "bdfresh"),
                    help="short path for the clean copies (Windows path-length limits apply)")
    ap.add_argument("--keep", action="store_true", help="keep the clean copies and environments")
    a = ap.parse_args()
    work = Path(a.workdir)
    work.mkdir(parents=True, exist_ok=True)
    ref_hash = panel_hash(V2 / "data" / "gold" / "bangladesh_agri_v2.duckdb")
    summary = dict(date_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                   machine=dict(os=platform.platform(terse=True), cpus=os.cpu_count()),
                   reference_panel_sha256=ref_hash, environments={})
    for name, req in ENVS.items():
        print(f"environment {name} ({req}) ...", flush=True)
        r = test_env(name, req, work, ref_hash)
        summary["environments"][name] = r
        print(f"  install {r['install_exit']}, run_all {r['run_all_exit']} ({r['run_all_s']} s), "
              f"failure tests {r['failure_cases_passed']}, baseline {r['baseline']}, validation {r['validation']}, "
              f"comparison {r['comparison']}", flush=True)
    (DOCS / "fresh_setup_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)
    ok = all(r["run_all_exit"] == 0 and r["failure_tests_exit"] == 0 and r["compare_exit"] == 0
             and r["panel_sha256_matches"] for r in summary["environments"].values())
    print("fresh-setup test", "PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
