"""Step 3 - Silver and Gold layers.

Silver: one tidy parquet per source keyed on (district, harvest_year), with
range validation.  Gold: DuckDB tables used by every analysis and the
dashboard.  The panel contains BBS-observed yields only; no value is
imputed, interpolated or modelled.  Missing inputs stay NULL.
"""
import duckdb
import geopandas as gpd
import pandas as pd

from common import BRONZE, CANONICAL, LOGS, V2_BRONZE, V2_GOLD, V2_SILVER, DataContractError, canon_district
from schema import BRONZE_FILES, COVERAGE, RANGES, REQUIRED_NONNULL

GEE = V2_BRONZE / "gee"
NUMERIC = ["harvest_year", "area_ha", "yield_t_ha", "production_t", "book_year", "page", *COVERAGE]


def records(df, mask, col=None, n=5):
    """Label up to n records for a diagnostic: district and year, and the
    offending value of col."""
    keys = [k for k in ("district", "harvest_year", "crop_year") if k in df.columns][:2]
    out = []
    for i, r in df[mask].head(n).iterrows():
        label = " ".join(str(r[k]) for k in keys) or f"row {i + 2}"
        out.append(f"{label} = {r[col]!r}" if col else label)
    return f"{int(mask.sum())} record(s): " + ", ".join(out)


def check_inputs():
    """Schema contract for the Bronze inputs, checked before anything is
    joined: files present, required columns present, numeric columns numeric,
    required values present."""
    problems, missing_values = [], []
    for rel, cols in BRONZE_FILES.items():
        if rel == "bbs/bbs_boro_rows_all.csv":
            continue                                    # extraction log, not an input here
        f = V2_BRONZE / rel
        if not f.exists():
            problems.append(f"{rel}: file missing")
            continue
        # Only an empty cell counts as missing; text such as "n/a" or "-" is
        # kept as text so that it fails the numeric-type check below.
        df = pd.read_csv(f, keep_default_na=False, na_values=[""])
        for c in REQUIRED_NONNULL.get(rel, []):
            if c in df.columns and df[c].isna().any():
                missing_values.append(f"{rel}.{c} empty in {records(df, df[c].isna())}")
        need = list(cols)
        if rel.startswith("gee/"):
            ext = rel.split("/")[1].split("_")[0]
            need += [v for v, (src, _, _) in COVERAGE.items() if src == ext]
        missing = [c for c in need if c not in df.columns]
        if missing:
            problems.append(f"{rel}: missing required columns {missing}")
        bad_type = [c for c in need if c in df.columns and c in NUMERIC
                    and not pd.api.types.is_numeric_dtype(df[c])]
        if bad_type:
            where = "; ".join(f"{c} in {records(df, pd.to_numeric(df[c], errors='coerce').isna() & df[c].notna(), c)}"
                              for c in bad_type)
            problems.append(f"{rel}: non-numeric values in numeric columns {bad_type}: {where}")
    if problems:
        raise DataContractError("[SCHEMA] " + "; ".join(problems))
    if missing_values:
        raise DataContractError("[MISSING] " + "; ".join(missing_values))


def harmonise(df, name):
    """Map source district names to the gazetteer; stop on any name that is
    not recognised rather than letting the row drop out at the join."""
    mapped = df.district.map(canon_district)
    unknown = sorted(df.district[mapped.isna()].astype(str).unique())
    if unknown:
        raise DataContractError(f"[DISTRICT] {name}: unrecognised district names {unknown} in "
                                f"{records(df, mapped.isna())}; "
                                "check the source and add the spelling to common.ALIASES")
    return df.assign(district=mapped)


def validate(df, name, log):
    for c, (lo, hi) in RANGES.items():
        if c in df:
            bad = df[df[c].notna() & ~df[c].between(lo, hi)]
            log.append(f"{name}: {c} out of [{lo},{hi}]: {len(bad)}")
            if len(bad):
                recs = ", ".join(f"{r.district} {r.harvest_year} = {getattr(r, c)}" for r in bad.head(5).itertuples())
                raise DataContractError(f"[RANGE] {name}.{c} outside [{lo}, {hi}] in {len(bad)} record(s): {recs}")
    dup = df[df.duplicated(["district", "harvest_year"], keep=False)]
    log.append(f"{name}: duplicate district-years: {len(dup)}")
    if len(dup):
        keys = sorted(set(zip(dup.district, dup.harvest_year)))
        raise DataContractError(f"[KEY] {name}: duplicate (district, harvest_year) keys {keys}")


def main():
    log = []
    check_inputs()
    # ── Silver ──────────────────────────────────────────────────────────
    bbs = harmonise(pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_district_year.csv"), "bbs")
    bbs = bbs[["district", "harvest_year", "crop_year", "area_ha", "yield_t_ha",
               "production_t", "book_year", "page"]].rename(
        columns={"book_year": "bbs_edition", "page": "bbs_page"})
    nat = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_national.csv")
    nat = (nat.sort_values("book_year").drop_duplicates("crop_year", keep="last")
           .assign(harvest_year=lambda x: x.crop_year.str[:4].astype(int) + 1))

    silver = {"bbs_boro": bbs}
    for name in ["ndvi", "climate", "jrc", "s1"]:
        silver[name] = harmonise(pd.read_csv(GEE / f"{name}_all.csv"), name)
    for name, df in silver.items():
        validate(df, name, log)
        df.to_parquet(V2_SILVER / f"silver_{name}.parquet", index=False)

    g = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_2.shp")
    g = harmonise(g.rename(columns={"NAME_2": "district"}), "gadm")
    g["division"] = g.NAME_1.replace({"Barisal": "Barishal", "Chittagong": "Chattogram"})
    # rounded to 0.001 km² so the value does not depend on the last floating-point
    # digit of the installed shapely/pyproj versions
    g["area_km2"] = (g.to_crs(32646).area / 1e6).round(3)
    assert sorted(g.district) == sorted(CANONICAL)
    dim = pd.DataFrame(g[["GID_2", "district", "division", "area_km2"]]).rename(columns={"GID_2": "district_id"})

    # ── Gold ────────────────────────────────────────────────────────────
    con = duckdb.connect(str(V2_GOLD))
    for name, df in silver.items():
        con.register("tmp", df)
        con.execute(f"CREATE OR REPLACE TABLE stg_{name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.register("tmp", dim)
    con.execute("CREATE OR REPLACE TABLE dim_district AS SELECT * FROM tmp")
    con.unregister("tmp")
    # National series from district sums (all 15 years), with the printed
    # national row alongside wherever an edition prints one.
    con.register("tmp", nat[["harvest_year", "area_ha", "yield_t_ha", "production_t"]])
    con.execute("""
        CREATE OR REPLACE TABLE fact_boro_national AS
        SELECT b.harvest_year, any_value(b.crop_year) AS crop_year,
               sum(b.area_ha) AS area_ha, sum(b.production_t) AS production_t,
               sum(b.production_t) / sum(b.area_ha) AS yield_t_ha,
               any_value(t.production_t) AS printed_national_production_t,
               any_value(t.yield_t_ha) AS printed_national_yield_t_ha
        FROM stg_bbs_boro b LEFT JOIN tmp t USING (harvest_year)
        GROUP BY b.harvest_year ORDER BY b.harvest_year
    """)
    con.unregister("tmp")

    con.execute("""
        CREATE OR REPLACE TABLE fact_boro_panel AS
        SELECT d.district_id, b.district, d.division, d.area_km2, b.harvest_year, b.crop_year,
               b.yield_t_ha, b.area_ha, b.production_t, b.bbs_edition, b.bbs_page,
               n.ndvi_peak, n.ndvi_max,
               c.tmean_c, c.tmax_c, c.precip_mm, c.hot_days,
               j.jrc_monsoon_flood, j.jrc_flash_flood, j.jrc_monsoon_obs, j.jrc_flash_obs,
               s.s1_monsoon_flood, s.s1_flash_flood
        FROM stg_bbs_boro b
        JOIN dim_district d USING (district)
        LEFT JOIN stg_ndvi n USING (district, harvest_year)
        LEFT JOIN stg_climate c USING (district, harvest_year)
        LEFT JOIN stg_jrc j USING (district, harvest_year)
        LEFT JOIN stg_s1 s USING (district, harvest_year)
        ORDER BY b.district, b.harvest_year
    """)
    panel = con.execute("SELECT * FROM fact_boro_panel").df()
    con.close()

    full = pd.MultiIndex.from_product([sorted(CANONICAL), range(2011, 2026)], names=["district", "harvest_year"])
    absent = full.difference(pd.MultiIndex.from_frame(panel[["district", "harvest_year"]]))
    if len(absent):
        raise DataContractError(f"[MISSING] fact_boro_panel: no BBS value for {len(absent)} district-year(s): "
                                + ", ".join(f"{d} {y}" for d, y in absent[:5]))
    assert len(panel) == 64 * 15 and not panel.duplicated(["district", "harvest_year"]).any()
    log.append(f"fact_boro_panel: {len(panel)} rows, {panel.district.nunique()} districts, "
               f"{panel.harvest_year.min()}-{panel.harvest_year.max()}")
    log.append("Non-missing counts:\n" + panel.notna().sum().to_string())
    (LOGS / "s03_build_panel.log").write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
