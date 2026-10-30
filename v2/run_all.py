"""Rebuild the v2 pipeline end to end: python v2/run_all.py

Records the run time of each step in v2/outputs/pipeline_timings.json
(Earth Engine steps are timed per variable-year when first extracted; see
data/bronze/gee/extraction_times.json).
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

V2 = Path(__file__).parent
SRC = V2 / "src"
STEPS = [("BBS extraction and validation", "s01_bbs_extract.py"),
         ("Earth Engine extraction (cached)", "s02_gee_extract.py"),
         ("Metadata manifest", "s02b_manifest.py"),
         ("Silver and Gold layers", "s03_build_panel.py"),
         ("Validation report", "s03b_validate.py"),
         ("Statistical analysis", "s04_analysis.py"),
         ("Figures", "s05_figures.py"),
         ("Manuscript template", "make_reference_docx.py")]
MANUSCRIPTS = ["paper_ems"]


def ram_gb():
    try:
        import ctypes

        class MEM(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        m = MEM()
        m.len = ctypes.sizeof(MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.total / 2**30)
    except Exception:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30)


def run(script, *args):
    t0 = time.time()
    subprocess.run([sys.executable, "-W", "ignore", script, *args], cwd=SRC, check=True)
    return time.time() - t0


def main():
    local = {}
    for label, script in STEPS:
        print(f"\n=== {script} ===", flush=True)
        local[label] = round(run(script), 1)
    gee = json.loads((V2 / "data" / "bronze" / "gee" / "extraction_times.json").read_text())
    per = {}
    for k, v in gee.items():
        per.setdefault(k.rsplit("_", 1)[0], []).append(v)
    names = {"ndvi": "NDVI", "climate": "ERA5-Land climate", "jrc": "JRC flood", "s1": "Sentinel-1 flood"}
    timings = dict(
        local_s=local,
        gee_s_per_year={names.get(k, k): round(sum(v) / len(v), 0) for k, v in per.items()},
        machine=dict(os=platform.platform(terse=True), cpus=os.cpu_count(), ram_gb=ram_gb(),
                     python=platform.python_version()))
    (V2 / "outputs" / "pipeline_timings.json").write_text(json.dumps(timings, indent=1))
    if shutil.which("pandoc") is None:
        print("\npandoc not found: skipping the manuscript build (all data and analysis outputs are complete)")
        return
    for paper in MANUSCRIPTS:
        print(f"\n=== s06_manuscript.py {paper} ===", flush=True)
        run("s06_manuscript.py", paper)


if __name__ == "__main__":
    main()
