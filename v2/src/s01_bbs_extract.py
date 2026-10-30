"""Step 1 - Extract district-level Total Boro (Local+HYV+Hybrid) estimates
from every BBS Yearbook of Agricultural Statistics (2012-2025 editions).

Every value is read from the printed table; nothing is imputed.  Each row is
checked three ways (acres<->hectares, maund/acre<->t/ha, area x yield =
production), each yearbook's district sum is checked against its printed
national total, and years printed in two editions are compared.

With --from-rows FILE the PDFs are not read: the parsed rows are taken from
FILE (a bbs_boro_rows_all.csv) and every step after parsing is rerun. The
failure tests use this to check what the identity, total and edition checks
do with deliberately damaged rows.

Outputs (v2/data/bronze/bbs):
  bbs_boro_rows_all.csv      every parsed row, all editions, with QC flags
  bbs_boro_national.csv      printed national totals per edition/year
  bbs_boro_district_year.csv one row per district x crop year (later edition)
  bbs_edition_diffs.csv      district-years whose values differ between editions
"""
import re
import sys
import warnings
from pathlib import Path

import camelot
import numpy as np
import pandas as pd

from common import BRONZE, V2_BRONZE, canon_district
from schema import BBS_PAGES

warnings.filterwarnings("ignore")

PDF_DIR = BRONZE / "bbs" / "pdfs"
OUT = V2_BRONZE / "bbs"
OUT.mkdir(parents=True, exist_ok=True)

# Pages (1-based) holding the "Total Boro (Local+HYV+Hybrid)" district table,
# located by searching each yearbook's table titles.
PAGES = BBS_PAGES                 # edition -> PDF pages of the Total Boro table

ACRE_HA = 0.404686           # hectares per acre
MAUND_T = 0.0373242          # tonnes per maund (37.3242 kg)
TOL = 0.005                  # maximum relative discrepancy for each identity (0.5 %)
YEAR_RE = re.compile(r"(20\d\d)\s*-\s*(?:20)?(\d\d)(?!\d)")


def to_num(s):
    s = str(s).replace(",", "").replace("\n", "").strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return float(s)
    return None


def parse_table(df, book, page):
    header = " ".join(df.iloc[:3].astype(str).values.ravel())
    years = []
    for a, b in YEAR_RE.findall(header):
        cy = f"{a}-{b}"
        if cy not in years:
            years.append(cy)
    rows = []
    for _, r in df.iterrows():
        cells = [str(c).replace("\n", " ").strip() for c in r.tolist()]
        nums, name_parts = [], []
        for c in cells:
            v = to_num(c)
            if v is None:
                if c:
                    name_parts.append(c)
            elif name_parts or nums:            # skip leading serial numbers
                nums.append(v)
        name = re.sub(r"^\d+\s*", "", " ".join(name_parts)).strip()
        if not name or len(nums) not in (5, 10):
            continue
        blocks = [nums[i:i + 5] for i in range(0, len(nums), 5)]
        if len(blocks) != len(years):
            # Crop years are read from the table header and never assigned by position
            raise ValueError(f"{book} edition, page {page}: row '{name}' has {len(blocks)} crop-year block(s) "
                             f"but the table header gives {len(years)} crop year(s) {years}; check the table")
        for cy, (acre, ha, maund, tha, prod) in zip(years, blocks):
            rows.append(dict(book_year=book, page=page, raw_name=name, crop_year=cy,
                             area_acres=acre, area_ha=ha, yield_maund_acre=maund,
                             yield_t_ha=tha, production_t=prod))
    return rows


RAW_COLS = ["book_year", "page", "raw_name", "crop_year", "area_acres", "area_ha",
            "yield_maund_acre", "yield_t_ha", "production_t"]
SINGLE_TAG = " [single-district region]"


def parse_pdfs():
    rows = []
    for book, pages in PAGES.items():
        pdf = PDF_DIR / f"bbs_agri_yearbook_{book}.pdf"
        tables = camelot.read_pdf(str(pdf), pages=pages, flavor="lattice")
        for t in tables:
            rows += parse_table(t.df, book, t.page)
        print(f"{book}: {len(tables)} tables")
    return pd.DataFrame(rows)


def load_rows(path):
    """Parsed rows saved by an earlier run, reduced to the printed values."""
    d = pd.read_csv(path)[RAW_COLS]
    d["raw_name"] = d.raw_name.str.replace(SINGLE_TAG, "", regex=False)
    return d


def classify(d):
    """Row types, district names and the three unit identities of parsed rows."""
    # The 2012 and 2013 editions group districts under former "greater
    # district" regions.  Five regions contain exactly one present-day
    # district and print no district row beneath them, so the region row
    # *is* that district's printed estimate.
    single = {"bandarbanregion": "Bandarban", "khagrachariregion": "Khagrachhari",
              "rangamatiregion": "Rangamati", "mymenshingregion": "Mymensingh",
              "tangailregion": "Tangail"}
    key = d.raw_name.str.lower().str.replace(r"[^a-z]", "", regex=True)
    is_single = d.book_year.isin([2012, 2013]) & key.isin(single)
    d["district"] = d.raw_name.map(canon_district)
    d.loc[is_single, "district"] = key[is_single].map(single)
    d.loc[is_single, "raw_name"] = d.loc[is_single, "raw_name"] + SINGLE_TAG
    name_l = d.raw_name.str.lower()
    d["row_type"] = np.where(name_l.str.contains("bangladesh|national"), "national",
                     np.where(name_l.str.contains("division|divison|region") & ~is_single, "division",
                     np.where(d.district.notna(), "district", "unknown")))
    # Arithmetic QC: relative discrepancy of each printed value against the
    # value implied by the other columns.  A row is accepted only if all three
    # are within TOL; failing rows are excluded automatically (no manual edits).
    d["qc_ha"] = (d.area_acres * ACRE_HA - d.area_ha).abs() / d.area_ha
    d["qc_yield"] = (d.yield_maund_acre * MAUND_T / ACRE_HA - d.yield_t_ha).abs() / d.yield_t_ha
    d["qc_prod"] = (d.area_ha * d.yield_t_ha - d.production_t).abs() / d.production_t
    d["qc_pass"] = (d.qc_ha <= TOL) & (d.qc_yield <= TOL) & (d.qc_prod <= TOL)
    return d


def main():
    if "--from-rows" in sys.argv:
        d = classify(load_rows(Path(sys.argv[sys.argv.index("--from-rows") + 1])))
    else:
        d = classify(parse_pdfs())
    d.to_csv(OUT / "bbs_boro_rows_all.csv", index=False)
    unknown = d[d.row_type == "unknown"].raw_name.unique()
    if len(unknown):
        # Never assign or drop an unrecognised row silently: stop so that the
        # spelling can be added to the gazetteer after checking the source.
        raise ValueError(f"unrecognised row names in BBS tables: {list(unknown)}; "
                         "add them to common.ALIASES after checking the yearbook")

    nat = d[d.row_type == "national"][["book_year", "crop_year", "area_ha", "yield_t_ha", "production_t"]]
    nat.to_csv(OUT / "bbs_boro_national.csv", index=False)

    dist = d[d.row_type == "district"].copy()
    # A district row without a crop year, or a district printed twice in one
    # table, stops the run: rows are never dropped or chosen silently.
    if dist.crop_year.isna().any():
        bad = dist[dist.crop_year.isna()]
        raise ValueError("district rows without a crop year: " + ", ".join(
            f"{r.district} ({int(r.book_year)} edition, page {int(r.page)})" for r in bad.head(5).itertuples()))
    dup = dist[dist.duplicated(["book_year", "crop_year", "district"], keep=False)]
    if len(dup):
        raise ValueError("district printed more than once in one table: " + ", ".join(
            f"{r.district} ({int(r.book_year)} edition, {r.crop_year}, page {int(r.page)})"
            for r in dup.head(6).itertuples()))

    # District sum vs printed national total, per edition and year
    s = dist.groupby(["book_year", "crop_year"]).agg(
        n_districts=("district", "nunique"), sum_prod=("production_t", "sum"),
        sum_area=("area_ha", "sum"), n_qc_fail=("qc_pass", lambda x: int((~x).sum())))
    s = s.join(nat.set_index(["book_year", "crop_year"])[["production_t", "area_ha"]]
               .rename(columns={"production_t": "national_prod", "area_ha": "national_area"}))
    s["prod_gap_pct"] = 100 * (s.sum_prod / s.national_prod - 1)
    s.to_csv(OUT / "bbs_edition_checks.csv")
    print(s.to_string())

    # Compare editions where a crop year is printed twice
    keys = ["district", "crop_year"]
    multi = dist[dist.duplicated(keys, keep=False)].sort_values(keys + ["book_year"])
    diffs = []
    for (dn, cy), g in multi.groupby(keys):
        a, b = g.iloc[0], g.iloc[-1]
        if abs(a.yield_t_ha - b.yield_t_ha) > 0.0005 or abs(a.area_ha - b.area_ha) > 0.5:
            diffs.append(dict(district=dn, crop_year=cy, early_book=a.book_year,
                              late_book=b.book_year, early_yield=a.yield_t_ha,
                              late_yield=b.yield_t_ha, early_area=a.area_ha, late_area=b.area_ha))
    pd.DataFrame(diffs).to_csv(OUT / "bbs_edition_diffs.csv", index=False)
    print(f"District-years printed in two editions: {multi[keys].drop_duplicates().shape[0]}, "
          f"differing: {len(diffs)}")

    # Geographic checks for the region-structured 2012 and 2013 editions:
    # (a) each multi-district region row equals the sum of the district rows
    #     listed under it, so regions partition into the listed districts;
    # (b) each single-district region row equals the district row printed for
    #     the same crop year (2012-13) in the district-structured 2014 edition.
    geo = []
    for (b, cy), g in d[d.book_year.isin([2012, 2013])].groupby(["book_year", "crop_year"], sort=False):
        g = g.reset_index(drop=True)
        start = 0
        for i, r in g.iterrows():
            single = "single-district" in r.raw_name
            if (r.row_type == "division" and "region" in r.raw_name.lower()) or single:
                block = g.iloc[start:i]
                block = block[block.row_type == "district"]
                if not single and len(block):
                    geo.append(dict(check="region = sum of listed districts", book_year=b, crop_year=cy,
                                    unit=r.raw_name, districts=", ".join(block.district),
                                    region_area_ha=r.area_ha, compare_area_ha=block.area_ha.sum(),
                                    region_production_t=r.production_t,
                                    compare_production_t=block.production_t.sum()))
                start = i + 1
    later = d[(d.book_year == 2014) & (d.row_type == "district")].set_index(["district", "crop_year"])
    for _, r in d[d.raw_name.str.contains("single-district")].iterrows():
        if (r.district, r.crop_year) in later.index:
            x = later.loc[(r.district, r.crop_year)]
            geo.append(dict(check="single-district region = 2014 district row", book_year=r.book_year,
                            crop_year=r.crop_year, unit=r.raw_name, districts=r.district,
                            region_area_ha=r.area_ha, compare_area_ha=x.area_ha,
                            region_production_t=r.production_t, compare_production_t=x.production_t))
    geo = pd.DataFrame(geo)
    # Printed values are rounded to whole units, so a sum of k rows may differ
    # from the printed total by up to 0.5 x (k + 1).
    tol = 0.5 * (geo.districts.str.count(",") + 2)
    geo["match"] = ((geo.region_area_ha - geo.compare_area_ha).abs() <= tol) & \
                   ((geo.region_production_t - geo.compare_production_t).abs() <= tol)
    geo.to_csv(OUT / "bbs_region_checks.csv", index=False)
    print(geo.groupby("check").match.agg(["size", "sum"]).to_string())
    assert geo.match.all(), "region rows do not reconcile with district rows"

    # Final: one row per district-year, taking the later (revised) edition
    # among rows that pass the arithmetic QC.
    fails = dist[~dist.qc_pass].copy()
    fails["failed_checks"] = fails.apply(lambda r: ", ".join(
        n for n, c in [("area", r.qc_ha), ("yield", r.qc_yield), ("production", r.qc_prod)] if c > TOL), axis=1)
    fails.to_csv(OUT / "bbs_qc_failures.csv", index=False)
    accepted = dist[dist.qc_pass]
    print("max relative discrepancy among accepted rows:",
          accepted[["qc_ha", "qc_yield", "qc_prod"]].max().round(5).to_dict())
    good = dist[dist.qc_pass].sort_values("book_year")
    final = good.drop_duplicates(keys, keep="last").copy()
    final["harvest_year"] = final.crop_year.str[:4].astype(int) + 1
    final = final.sort_values(["harvest_year", "district"])
    final.to_csv(OUT / "bbs_boro_district_year.csv", index=False)
    cov = final.groupby("crop_year").district.nunique()
    print("Districts per crop year (final):\n", cov.to_string())
    print("QC failures (excluded):", int((~dist.qc_pass).sum()))


if __name__ == "__main__":
    main()
