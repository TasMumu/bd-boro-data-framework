"""Step 3b - Validation report, district crosswalk and data dictionary.

Runs after the Gold layer is built.  Every check is written to
outputs/validation_report.csv with its category, expected condition,
observed result and status (PASS, FAIL or INFO).  Any FAIL stops the
pipeline.  Also writes:
  mappings/district_crosswalk.csv       every source spelling -> district
  outputs/tables/table_district_matching.csv
  docs/data_dictionary.md               generated from schema.py
"""
import hashlib
import json
import re
import sys

import duckdb
import geopandas as gpd
import pandas as pd

from common import ALIASES, BRONZE, CANONICAL, TABLES as OUT_TABLES, V2, V2_BRONZE, V2_GOLD, canon_district
from schema import BRONZE_FILES, COVERAGE, PRODUCTS, RANGES, TABLES

REPORT = []
TYPES = {"VARCHAR": "VARCHAR", "BIGINT": "BIGINT", "INTEGER": "BIGINT", "DOUBLE": "DOUBLE"}
# National totals quoted in the yearbook text for crop years whose tables
# print no national row (2012 edition p. 82; 2022 edition p. 91), with the
# precision of the printed figure: "186.17 lac" is given to 0.01 lakh
# (1,000 t), "201,85,945" to 1 t.
TEXT_TOTALS = {"2010-11": (18_617_000, 1000), "2021-22": (20_185_945, 1)}


def check(category, layer, obj, test, expected, observed, ok, affected=0, status=None):
    REPORT.append(dict(category=category, layer=layer, object=obj, check=test, expected=expected,
                       observed=observed, affected_records=int(affected),
                       status=status or ("PASS" if ok else "FAIL")))


def norm(s):
    return re.sub(r"[^a-z]", "", str(s).lower())


# ── District crosswalk and matching metrics ───────────────────────────────
def crosswalk(dim):
    gid = dict(zip(dim.district, dim.district_id))
    rows = []
    bbs = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_rows_all.csv")
    bbs = bbs[bbs.row_type == "district"]
    for raw, g in bbs.groupby("raw_name"):
        single = "[single-district region]" in raw
        printed = raw.replace(" [single-district region]", "")
        rows.append(dict(source="BBS yearbooks", source_name=printed, canonical_district=g.district.iloc[0],
                         single=single, n_records=len(g),
                         editions=f"{g.book_year.min()}–{g.book_year.max()}"))
    gadm = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_2.shp")
    for name in gadm.NAME_2:
        rows.append(dict(source="GADM v4.1", source_name=name, canonical_district=canon_district(name),
                         single=False, n_records=1, editions=""))
    for ext in ["ndvi", "climate", "jrc", "s1"]:
        df = pd.read_csv(V2_BRONZE / "gee" / f"{ext}_all.csv")
        for name, g in df.groupby("district"):
            rows.append(dict(source=f"Earth Engine extract ({ext})", source_name=name,
                             canonical_district=canon_district(name), single=False, n_records=len(g), editions=""))
    cw = pd.DataFrame(rows)

    def rule(r):
        if r.canonical_district is None or pd.isna(r.canonical_district):
            return "unmatched"
        if r.single:
            return "single-district region row (verified against 2014 edition)"
        if r.source_name == r.canonical_district:
            return "exact"
        if norm(r.source_name) == norm(r.canonical_district):
            return "normalised (case, spacing, punctuation)"
        return "alias rule"
    cw["rule"] = cw.apply(rule, axis=1)
    cw["district_id"] = cw.canonical_district.map(gid)
    cw = cw.drop(columns="single").sort_values(["source", "canonical_district", "source_name"])
    (V2 / "mappings").mkdir(exist_ok=True)
    cw.to_csv(V2 / "mappings" / "district_crosswalk.csv", index=False)

    summary = []
    for src, g in cw.assign(group=cw.source.str.replace(r" \(.*\)", "", regex=True)).groupby("group", sort=False):
        u = g.drop_duplicates("source_name")          # count each distinct spelling once
        summary.append({"Source": src, "Records": int(g.n_records.sum()), "Distinct spellings": len(u),
                        "Exact": int((u.rule == "exact").sum()),
                        "Normalised": int((u.rule.str.startswith("normalised")).sum()),
                        "Alias rule": int((u.rule == "alias rule").sum()),
                        "Region row": int(u.rule.str.startswith("single").sum()),
                        "Unmatched": int((u.rule == "unmatched").sum()),
                        "Districts reached": g.canonical_district.nunique()})
    pd.DataFrame(summary).to_csv(OUT_TABLES / "table_district_matching.csv", index=False)

    unmatched = cw[cw.rule == "unmatched"]
    check("geographic", "Bronze", "all sources", "every source district name maps to the gazetteer",
          "0 unmatched", f"{len(unmatched)} unmatched", len(unmatched) == 0, unmatched.n_records.sum())
    amb = [k for k in ALIASES if k in {norm(c) for c in CANONICAL}]
    check("geographic", "Bronze", "gazetteer", "no alias rule repeats or collides with a canonical district name",
          "0", f"{len(amb)}", not amb, len(amb))
    gmap = cw[cw.source == "GADM v4.1"]
    check("geographic", "Bronze", "GADM v4.1", "GADM districts map one-to-one onto the 64 canonical districts",
          "64 distinct, all canonical", f"{gmap.canonical_district.nunique()} distinct",
          gmap.canonical_district.nunique() == 64 and set(gmap.canonical_district) == set(CANONICAL))
    for src, g in cw.groupby("source"):
        check("geographic", "Bronze", src, "source covers all 64 districts", "64",
              str(g.canonical_district.nunique()), g.canonical_district.nunique() == 64)
    # An unused rule is not an error (a source may drop a spelling), but the
    # gazetteer should hold only rules the data need.
    unused = sorted(set(ALIASES) - {norm(n) for n in cw.source_name})
    check("geographic", "Bronze", "gazetteer", "every alias rule matches a spelling in the sources",
          f"{len(ALIASES)} of {len(ALIASES)} used", f"{len(ALIASES) - len(unused)} of {len(ALIASES)} used",
          True, len(unused), status=None if not unused else "INFO")
    return cw


# ── Structural ────────────────────────────────────────────────────────────
def structural(con):
    for rel, cols in BRONZE_FILES.items():
        f = V2_BRONZE / rel
        if not f.exists():
            check("structural", "Bronze", rel, "file present", "present", "missing", False)
            continue
        df = pd.read_csv(f, nrows=5)
        need = list(cols)
        if rel.startswith("gee/"):
            ext = rel.split("/")[1].split("_")[0]
            need += [v for v, (src, _, _) in COVERAGE.items() if src == ext]
        missing = [c for c in need if c not in df.columns]
        check("structural", "Bronze", rel, "required columns present", f"{len(need)} columns",
              "missing " + ", ".join(missing) if missing else "all present", not missing)
    for t, spec in TABLES.items():
        actual = {r[0]: TYPES.get(r[1], r[1]) for r in con.execute(f"DESCRIBE {t}").fetchall()}
        want = {c[0]: c[1] for c in spec["columns"]}
        missing = [c for c in want if c not in actual]
        extra = [c for c in actual if c not in want]
        wrong = [f"{c} ({actual[c]}≠{want[c]})" for c in want if c in actual and actual[c] != want[c]]
        problems = ([f"missing {missing}"] if missing else []) + ([f"undocumented {extra}"] if extra else []) + wrong
        check("structural", "Gold", t, "columns and types match the data dictionary",
              f"{len(want)} documented columns", "; ".join(problems) or "match", not problems)


# ── Relational and temporal ───────────────────────────────────────────────
def relational(con):
    for t, spec in TABLES.items():
        key = ", ".join(spec["key"])
        n, nk = con.execute(f"SELECT count(*), count(DISTINCT ({key})) FROM {t}").fetchone()
        nulls = con.execute(f"SELECT count(*) FROM {t} WHERE " +
                            " OR ".join(f"{k} IS NULL" for k in spec["key"])).fetchone()[0]
        check("relational", "Gold", t, f"key ({key}) unique and not null", "unique, 0 null",
              f"{n - nk} duplicates, {nulls} null", n == nk and nulls == 0, (n - nk) + nulls)
        check("relational", "Gold", t, "row count", str(spec["rows"]), str(n), n == spec["rows"])
    nb = con.execute("SELECT count(*) FROM stg_bbs_boro").fetchone()[0]
    npn = con.execute("SELECT count(*) FROM fact_boro_panel").fetchone()[0]
    check("relational", "Gold", "fact_boro_panel", "joins neither multiply nor drop BBS rows",
          f"{nb} rows (= stg_bbs_boro)", str(npn), npn == nb, abs(npn - nb))
    for t in ["stg_bbs_boro", "stg_ndvi", "stg_climate", "stg_jrc", "stg_s1"]:
        orphan = con.execute(f"SELECT count(*) FROM {t} WHERE district NOT IN (SELECT district FROM dim_district)").fetchone()[0]
        check("relational", "Gold", t, "every district exists in dim_district", "0 orphans",
              f"{orphan} orphans", orphan == 0, orphan)
        lost = con.execute(f"""SELECT count(*) FROM {t} s WHERE NOT EXISTS (SELECT 1 FROM fact_boro_panel p
                               WHERE p.district = s.district AND p.harvest_year = s.harvest_year)""").fetchone()[0]
        check("relational", "Gold", t, "every staging record reaches the panel", "0 lost",
              f"{lost} lost", lost == 0, lost)
    for v, (src, _, _) in COVERAGE.items():
        a = con.execute(f"SELECT count({v}) FROM stg_{src}").fetchone()[0]
        b = con.execute(f"SELECT count({v}) FROM fact_boro_panel").fetchone()[0]
        check("relational", "Gold", "fact_boro_panel", f"{v}: non-missing values preserved by the join",
              str(a), str(b), a == b, abs(a - b))


def temporal(con):
    bad = con.execute("""SELECT count(*) FROM stg_bbs_boro
                         WHERE harvest_year <> CAST(substr(crop_year, 1, 4) AS INTEGER) + 1""").fetchone()[0]
    check("temporal", "Gold", "stg_bbs_boro", "harvest year = first year of BBS crop year + 1",
          "0 violations", f"{bad} violations", bad == 0, bad)
    yrs = con.execute("SELECT harvest_year, count(DISTINCT district) FROM fact_boro_panel GROUP BY 1 ORDER BY 1").fetchall()
    ok = [y for y, _ in yrs] == list(range(2011, 2026)) and all(n == 64 for _, n in yrs)
    missing = con.execute("""SELECT d.district, y.harvest_year FROM dim_district d
                             CROSS JOIN range(2011, 2026) y(harvest_year)
                             ANTI JOIN fact_boro_panel p ON p.district = d.district AND p.harvest_year = y.harvest_year
                             ORDER BY 2, 1""").fetchall()
    check("temporal", "Gold", "fact_boro_panel", "15 consecutive harvest years, 64 districts each",
          "2011–2025 × 64", f"{yrs[0][0]}–{yrs[-1][0]}, {min(n for _, n in yrs)}–{max(n for _, n in yrs)} districts"
          + (f"; missing: {', '.join(f'{d} {y}' for d, y in missing[:5])}" if missing else ""),
          ok and not missing, len(missing))
    for v, (src, y0, y1) in COVERAGE.items():
        inside, outside = con.execute(f"""SELECT count(*) FILTER (WHERE harvest_year BETWEEN {y0} AND {y1} AND {v} IS NULL),
                                                 count(*) FILTER (WHERE harvest_year NOT BETWEEN {y0} AND {y1} AND {v} IS NOT NULL)
                                          FROM fact_boro_panel""").fetchone()
        check("temporal", "Gold", "fact_boro_panel", f"{v}: values present exactly for harvest years {y0}–{y1}",
              "0 gaps inside, 0 values outside", f"{inside} gaps, {outside} outside",
              inside == 0 and outside == 0, inside + outside)


def values(con):
    n = con.execute("""SELECT count(*) FROM fact_boro_panel
                       WHERE yield_t_ha IS NULL OR area_ha IS NULL OR production_t IS NULL""").fetchone()[0]
    check("value", "Gold", "fact_boro_panel", "BBS area, yield and production present in every row",
          "0 missing", f"{n} rows with a missing BBS value", n == 0, n)
    for v, (lo, hi) in RANGES.items():
        n = con.execute(f"SELECT count(*) FROM fact_boro_panel WHERE {v} IS NOT NULL AND ({v} < {lo} OR {v} > {hi})").fetchone()[0]
        check("value", "Gold", "fact_boro_panel", f"{v} within [{lo}, {hi}]", "0 outside", f"{n} outside", n == 0, n)


def lineage(con):
    n = con.execute("SELECT count(*) FROM fact_boro_panel WHERE bbs_edition IS NULL OR bbs_page IS NULL").fetchone()[0]
    check("lineage", "Gold", "fact_boro_panel", "every BBS value records its yearbook edition and page",
          "0 missing", f"{n} missing", n == 0, n)
    # The manifest records a SHA-256 for every source file and extract; a
    # mismatch means a file changed after the manifest was written.
    m = pd.read_csv(V2_BRONZE / "manifest.csv")
    stale, absent = [], []
    for r in m.itertuples():
        p = (V2 / r.file[3:]) if r.file.startswith("v2/") else (BRONZE.parents[1] / r.file)
        if not p.exists():
            absent.append(r.file)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != r.sha256:
            stale.append(r.file)
    check("lineage", "Bronze", "manifest.csv", "every listed file present with the recorded SHA-256",
          f"{len(m)} files match", f"{len(m) - len(stale) - len(absent)} match, {len(stale)} changed, "
          f"{len(absent)} absent", not stale and not absent, len(stale) + len(absent))
    ext = m[m.kind == "Earth Engine extract"]
    n_files = len(list((V2_BRONZE / "gee").glob("*_20*.csv")))
    check("lineage", "Bronze", "manifest.csv", "every Earth Engine extract is documented in the manifest",
          f"{n_files} extracts", f"{len(ext)} documented", len(ext) == n_files, abs(len(ext) - n_files))


# ── Geographic (boundaries) ───────────────────────────────────────────────
def geographic():
    g2 = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_2.shp")
    g0 = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_0.shp")
    check("geographic", "Bronze", "GADM level 2", "coordinate reference system", "EPSG:4326",
          str(g2.crs.to_string()), g2.crs.to_epsg() == 4326)
    bad = int((~g2.is_valid | g2.is_empty).sum())
    check("geographic", "Bronze", "GADM level 2", "64 valid, non-empty district polygons", "64 valid",
          f"{len(g2)} polygons, {bad} invalid or empty", len(g2) == 64 and bad == 0, bad)
    a2 = g2.to_crs(32646).area.sum() / 1e6
    a0 = g0.to_crs(32646).area.sum() / 1e6
    gap = abs(a2 / a0 - 1)
    check("geographic", "Bronze", "GADM level 2", "district areas sum to the national polygon area",
          "within 1 %", f"{100 * gap:.3f} % ({a2:,.0f} vs {a0:,.0f} km²)", gap < 0.01)


# ── Cross-source (BBS) ─────────────────────────────────────────────────────
def cross_source(con):
    b = V2_BRONZE / "bbs"
    rows = pd.read_csv(b / "bbs_boro_rows_all.csv")
    dist = rows[rows.row_type == "district"]
    fails = pd.read_csv(b / "bbs_qc_failures.csv")
    check("cross-source", "Bronze", "BBS rows", "unit identities (area, yield, production) within 0.5 %",
          "failures excluded and logged", f"{len(fails)} of {len(dist)} rows failed, excluded",
          True, len(fails), status="INFO")
    chk = pd.read_csv(b / "bbs_edition_checks.csv")
    comp = chk[(chk.n_districts == 64) & chk.national_prod.notna()]
    gap = comp.prod_gap_pct.abs().max()
    off = comp[comp.prod_gap_pct.abs() >= 0.001]
    check("cross-source", "Bronze", "BBS tables", "district sum = printed national total (complete tables)",
          "within 0.001 %", f"max {gap:.6f} % over {len(comp)} tables" + "".join(
              f"; {int(r.book_year)} edition, {r.crop_year}: {r.prod_gap_pct:+.3f} %" for r in off.itertuples()),
          gap < 0.001, len(off))
    final = pd.read_csv(b / "bbs_boro_district_year.csv")
    for cy, (total, precision) in TEXT_TOTALS.items():
        g = final[final.crop_year == cy]
        s = g.production_t.sum()
        # half the printed precision, plus 0.5 t for each rounded district value
        tol = precision / 2 + 0.5 * (len(g) + 1)
        check("cross-source", "Bronze", f"BBS {cy}", "district sum = total quoted in yearbook text",
              f"{total:,} ± {tol:,.1f} t", f"{s:,.0f} t", abs(s - total) <= tol)
    diffs = pd.read_csv(b / "bbs_edition_diffs.csv")
    da = (diffs.late_area - diffs.early_area).abs()
    dy = (diffs.late_yield - diffs.early_yield).abs()
    # Printed values are rounded: area to 1 ha, yield to 0.001 t/ha.
    big = diffs[(da > 1) | (dy > 0.0015)]
    check("cross-source", "Bronze", "BBS editions", "years printed in two editions agree",
          "differences within rounding (1 ha, 0.001 t/ha)",
          f"{len(big)} of {len(diffs)} differing pairs beyond rounding; largest differences "
          f"{(da.max() if len(diffs) else 0):,.0f} ha and {(dy.max() if len(diffs) else 0):.3f} t/ha" + "".join(
              f"; {r.district} {r.crop_year}: {int(r.early_book)} edition {r.early_area:,.0f} ha, {r.early_yield} t/ha; "
              f"{int(r.late_book)} edition {r.late_area:,.0f} ha, {r.late_yield} t/ha" for r in big.head(4).itertuples()),
          big.empty, len(big))
    reg = pd.read_csv(b / "bbs_region_checks.csv")
    for kind, g in reg.groupby("check"):
        check("cross-source", "Bronze", "BBS 2012–2013 editions", kind, "all match within rounding",
              f"{int(g.match.sum())} of {len(g)} match", bool(g.match.all()), int((~g.match).sum()))
    d = con.execute("""SELECT max(abs(yield_t_ha - printed_national_yield_t_ha)), count(printed_national_yield_t_ha)
                       FROM fact_boro_national""").fetchone()
    check("cross-source", "Gold", "fact_boro_national", "national yield from district sums = printed national yield",
          "within 0.001 t/ha", f"max {d[0]:.4f} t/ha over {d[1]} years", d[0] < 0.001)


# ── Data dictionary ───────────────────────────────────────────────────────
def data_dictionary(cw):
    L = ["# Data dictionary (v2)", "",
         "Generated by `src/s03b_validate.py` from `src/schema.py`; do not edit by hand.", "",
         "## Source inventory", "",
         "| Source | Provider | Format | Spatial | Product availability | Period used | Licence and access |",
         "|---|---|---|---|---|---|---|"]
    for p in PRODUCTS.values():
        L.append(f"| {p['name']} | {p['provider']} | {p['format']} | {p['spatial']} | {p['available']} | {p['used']} | {p['licence']} |")
    L += ["", "## Variable coverage in the panel", "", "| Variable | Extract | Harvest years with values |", "|---|---|---|"]
    for v, (src, y0, y1) in COVERAGE.items():
        L.append(f"| {v} | {src} | {y0}–{y1} |")
    for t, spec in TABLES.items():
        L += ["", f"## {t}", "", f"- Grain: {spec['grain']}", f"- Key: {', '.join(spec['key'])} (unique, not null)",
              f"- Expected rows: {spec['rows']}", f"- Source: {spec['source']}", "",
              "| Column | Type | Unit | Description |", "|---|---|---|---|"]
        for c in spec["columns"]:
            L.append(f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} |")
    L += ["", "## District crosswalk", "",
          f"`mappings/district_crosswalk.csv` lists all {len(cw)} source spellings and the rule that maps each "
          "to a canonical district and its GADM identifier."]
    (V2 / "docs").mkdir(exist_ok=True)
    (V2 / "docs" / "data_dictionary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    con = duckdb.connect(str(V2_GOLD), read_only=True)
    dim = con.execute("SELECT * FROM dim_district").df()
    cw = crosswalk(dim)
    structural(con)
    relational(con)
    temporal(con)
    values(con)
    lineage(con)
    geographic()
    cross_source(con)
    con.close()
    data_dictionary(cw)
    rep = pd.DataFrame(REPORT)
    rep.to_csv(V2 / "outputs" / "validation_report.csv", index=False)
    summary = rep.groupby(["category", "status"]).size().unstack(fill_value=0)
    (V2 / "outputs" / "validation_summary.json").write_text(
        json.dumps(dict(checks=len(rep), by_status=rep.status.value_counts().to_dict(),
                        by_category=summary.to_dict(orient="index")), indent=1), encoding="utf-8")
    print(summary.to_string())
    fails = rep[rep.status == "FAIL"]
    if len(fails):
        print(fails[["category", "object", "check", "expected", "observed"]].to_string())
        sys.exit(f"validation failed: {len(fails)} check(s)")


if __name__ == "__main__":
    main()
