"""Step 2b - Metadata manifest of every source file and extract.

Writes v2/data/bronze/manifest.csv with one row per file:
  BBS yearbook PDFs   edition, pages read, size, SHA-256
  GADM boundaries     file, size, SHA-256
  Earth Engine        product and version, bands, the exact date windows used
  extracts            for that harvest year, scale, mask, method, variables
                      present, rows, SHA-256
For extracts, extracted_utc is the date the extract was computed, recorded by
s02 in gee/extraction_dates.json (file modification times are not used: they
change when files are copied or cloned). PDFs and GADM files are identified
by SHA-256. Settings come from schema.py, the same specification the
extractor uses.
"""
import hashlib
import json
from importlib.metadata import version

import pandas as pd

from common import BRONZE, V2_BRONZE
from schema import BBS_PAGES, COVERAGE, EXTRACTS, PRODUCTS, window

# Which windows belong to which variables (a window is listed only if one of
# its variables is present for that harvest year).
WINDOW_VARS = {
    "ndvi": {"season": ["ndvi_peak", "ndvi_max"]},
    "climate": {"season": ["tmean_c", "tmax_c", "precip_mm"], "hot": ["hot_days"]},
    "jrc": {"monsoon": ["jrc_monsoon_flood"], "monsoon_dry": ["jrc_monsoon_flood"],
            "flash": ["jrc_flash_flood"], "flash_dry": ["jrc_flash_flood"]},
    "s1": {"monsoon": ["s1_monsoon_flood"], "monsoon_dry": ["s1_monsoon_flood"],
           "flash": ["s1_flash_flood"], "flash_dry": ["s1_flash_flood"]},
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    dates_file = V2_BRONZE / "gee" / "extraction_dates.json"
    dates = json.loads(dates_file.read_text()) if dates_file.exists() else {}
    rows = []
    for ed, pages in BBS_PAGES.items():
        f = BRONZE / "bbs" / "pdfs" / f"bbs_agri_yearbook_{ed}.pdf"
        rows.append(dict(kind="BBS yearbook PDF", file=f"data/bronze/bbs/pdfs/{f.name}",
                         product=PRODUCTS["bbs"]["name"], version=f"{ed} edition",
                         detail=f"Total Boro district table, PDF pages {pages}",
                         size_bytes=f.stat().st_size, sha256=sha256(f)))
    for f in sorted((BRONZE / "gadm_shapefiles").glob("gadm41_BGD_[02].*")):
        rows.append(dict(kind="GADM boundaries", file=f"data/bronze/gadm_shapefiles/{f.name}",
                         product=PRODUCTS["gadm"]["name"], version="4.1", detail="level 2 districts"
                         if "_2." in f.name else "level 0 national outline",
                         size_bytes=f.stat().st_size, sha256=sha256(f)))
    ee_version = version("earthengine-api")
    for name, e in EXTRACTS.items():
        for f in sorted((V2_BRONZE / "gee").glob(f"{name}_20*.csv")):
            year = int(f.stem.split("_")[1])
            df = pd.read_csv(f)
            present = [v for v, (src, _, _) in COVERAGE.items() if src == name and v in df.columns]
            wins = []
            for w, vars_ in WINDOW_VARS[name].items():
                if any(v in present for v in vars_):
                    a, b = window(year, *e["windows"][w])
                    wins.append(f"{w} {a} to {b} (exclusive)")
            params = {k: v for k, v in e.items() if k.endswith(("_c", "_db", "_m", "_deg")) and k != "scale_m"}
            rows.append(dict(kind="Earth Engine extract", file=f"v2/data/bronze/gee/{f.name}",
                             product=e["collection"], version=e["version"], harvest_year=year,
                             bands=e["bands"], windows="; ".join(wins), scale_m=e["scale_m"],
                             mask=e["mask"], method=e["method"],
                             parameters="; ".join(f"{k}={v}" for k, v in params.items()),
                             variables=", ".join(present), rows=len(df),
                             software=f"earthengine-api {ee_version}",
                             size_bytes=f.stat().st_size, sha256=sha256(f),
                             extracted_utc=dates.get(f.stem, "")))
    m = pd.DataFrame(rows)
    m.to_csv(V2_BRONZE / "manifest.csv", index=False)
    print(m.groupby("kind").size().to_string())


if __name__ == "__main__":
    main()
