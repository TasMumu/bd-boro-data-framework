"""Step 6 - Assemble the revised manuscript (Markdown -> .docx via pandoc).

Narrative parts live in v2/paper/parts/*.md.  Placeholders of the form
{{ expression }} are evaluated against results.json (as R) and the table
CSVs, so every number in the text comes from the analysis outputs.
Tables are generated here from the CSVs.
"""
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

from common import TABLES, V2, V2_BRONZE, panel_sha256

R = json.loads((V2 / "outputs" / "results.json").read_text(encoding="utf-8"))
REG = R["regressions"]


def fmt_p(p, d=3):
    return "< 0.001" if p < 0.001 else f"{p:.{d}f}"


def p_eq(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def coef(m, v, d=3):
    c = REG[m]["coef"][v]
    return f"{c['b']:+.{d}f} t/ha (SE {c['se']:.{d}f}, {p_eq(c['p'])}; Driscoll–Kraay {p_eq(c['p_dk'])})"


AP = R["regressions_area_prod"]
EX = R["sensitivity_excl_2017"]


def bbs_stats():
    rows = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_rows_all.csv")
    chk = pd.read_csv(V2_BRONZE / "bbs" / "bbs_edition_checks.csv")
    diffs = pd.read_csv(V2_BRONZE / "bbs" / "bbs_edition_diffs.csv")
    dist = rows[(rows.row_type == "district") & rows.crop_year.notna()]
    two = dist.groupby(["district", "crop_year"]).book_year.nunique()
    fails = dist[~dist.qc_pass]
    return dict(n_rows=len(dist), n_fail=int((~dist.qc_pass).sum()),
                fail_where=sorted({f"{b} edition, {c}" for b, c in zip(fails.book_year, fails.crop_year)}),
                n_edition_years=len(chk), n_nat=int(chk.national_prod.notna().sum()),
                n_complete=int((chk.n_districts == 64).sum()),
                incomplete=sorted({f"{int(b)} edition ({n} districts parsed)" for b, n in
                                   zip(chk.book_year, chk.n_districts) if n < 64}),
                n_nat_complete=int(((chk.n_districts == 64) & chk.national_prod.notna()).sum()),
                max_gap_pct=float(chk[chk.n_districts == 64].prod_gap_pct.abs().max()),
                n_two=int((two > 1).sum()), n_diff=len(diffs),
                max_area_diff=float((diffs.late_area - diffs.early_area).abs().max()) if len(diffs) else 0.0,
                max_e=float(dist[dist.qc_pass][["qc_ha", "qc_yield", "qc_prod"]].max().max()),
                fail_ey_min=float(fails.qc_yield.min()), fail_ey_max=float(fails.qc_yield.max()))


BBS = bbs_stats()
_c = pd.read_csv(V2_BRONZE / "bbs" / "bbs_edition_checks.csv")
_no = _c[(_c.n_districts == 64) & _c.national_prod.isna()]
_eds = sorted({int(b) for b in _no.book_year})
BBS.update(no_nat_editions=", ".join(map(str, _eds[:-1])) + f" and {_eds[-1]}" if len(_eds) > 1 else str(_eds[0]),
           no_nat_years=_no.crop_year.nunique(),
           no_nat_covered=len(set(_no.crop_year) & set(_c[_c.national_prod.notna()].crop_year)))


def minus(text):
    """Typographic minus sign for negative numbers in tables."""
    return text.replace("-", "−") if text.startswith("-") else text
_geo = pd.read_csv(V2_BRONZE / "bbs" / "bbs_region_checks.csv")
GEO = dict(n_sum=int(_geo.check.str.startswith("region").sum()),
           n_single=int(_geo.check.str.startswith("single").sum()), all_match=bool(_geo.match.all()))
assert GEO["all_match"], "region checks failed"
VI = pd.read_csv(TABLES / "table_vulnerability_index.csv").set_index("district")
TOP = VI[VI["rank"] <= 10]
EV = pd.read_csv(TABLES / "table_event_2017.csv").set_index("district").head(6)
DESC = pd.read_csv(TABLES / "table_descriptives.csv").set_index("variable")
_f = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_district_year.csv")
CHP = _f[_f.district == "Chandpur"].set_index("harvest_year").area_ha
NATSUM = _f.groupby("crop_year").production_t.sum().to_dict()


def pct(key, v, src=None):
    c = (src or AP)[key]["coef"][v]
    return (f"{100 * c['b']:+.1f} % (SE {100 * c['se']:.1f}, {p_eq(c['p'])}; "
            f"Driscoll–Kraay {p_eq(c['p_dk'])})")


def f(x, d=3):
    return f"{x:.{d}f}"


def w(n):
    """Small whole numbers in words, as in running text."""
    words = "zero one two three four five six seven eight nine ten".split()
    return words[n] if isinstance(n, int) and 0 <= n <= 10 else str(n)


def md_table(df):
    cols = list(df.columns)
    # Pandoc sizes pipe-table columns by the relative length of the dashes, so
    # make each proportional to its widest cell (or longest header word).
    def width(c):
        cells = [len(str(v)) + 3 for v in df[c] if not pd.isna(v)]
        head = max(len(w) for w in str(c).split()) + 4   # bold header words must not break
        return min(max([head] + cells + [6]), 26)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("-" * width(c) for c in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def table_alignment():
    rows = [("Boro yield", "BBS crop year (t−1)–t", "Harvest Apr–May t"),
            ("Peak-season NDVI", "MODIS composites", "Jan–Apr t"),
            ("Mean temperature, mean daily maximum, season precipitation", "ERA5-Land daily", "Nov t−1 – May t"),
            ("Hot days (Tmax > 35 °C)", "ERA5-Land daily", "Mar–May t"),
            ("Monsoon flood fraction", "JRC monthly / Sentinel-1", "Jun–Oct t−1, net of Jan–Mar t−1 water"),
            ("Flash flood fraction", "JRC monthly / Sentinel-1", "Apr–May t, net of Jan–Mar t water")]
    return md_table(pd.DataFrame(rows, columns=["Variable", "Source", "Window for harvest year t"]))


def table_bbs_checks():
    c = pd.read_csv(V2_BRONZE / "bbs" / "bbs_edition_checks.csv")
    f = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_district_year.csv")
    text_total_edition = {"2010-11": 2012, "2021-22": 2022}      # totals quoted in the yearbook text
    rows = []
    for cy, g in c.groupby("crop_year"):
        fin = f[f.crop_year == cy]
        checked = g[(g.n_districts == 64) & g.national_prod.notna()]
        if len(checked):
            gap = checked.prod_gap_pct.abs().max()
            chk = ("< 0.001 %" if gap < 0.001 else f"{gap:.3f} %") + \
                f" ({', '.join(str(int(b)) for b in checked.book_year)})"
        else:
            chk = f"matches text total ({text_total_edition.get(cy, '?')})"
        used = fin.book_year.value_counts().sort_index(ascending=False)
        rows.append({"Crop year": cy, "Harvest year": int(cy[:4]) + 1,
                     "Editions": ", ".join(str(int(b)) for b in g.book_year),
                     "Districts": fin.district.nunique(),
                     "Rows failing checks": int(g.n_qc_fail.sum()),
                     "Gap to national total (edition checked)": chk,
                     "Edition used": str(int(used.index[0])) if len(used) == 1 else
                     ", ".join(f"{int(b)} ({n})" for b, n in used.items())})
    return md_table(pd.DataFrame(rows))


def table_descriptives():
    d = pd.read_csv(TABLES / "table_descriptives.csv")
    for c in ["mean", "sd", "min", "max"]:
        d[c] = d[c].map(lambda x: minus(f"{x:,.0f}" if abs(x) >= 100 else f"{x:.3f}"))
    d["years"] = d.years.str.replace("-", "–")
    return md_table(d.rename(columns={"variable": "Variable", "years": "Harvest years", "n": "N",
                                      "mean": "Mean", "sd": "SD", "min": "Min", "max": "Max"}))


def table_fe():
    d = pd.read_csv(TABLES / "table_panel_fe.csv").fillna("")
    hdr = {m: f"{m} {REG[m]['title']}" for m in REG}
    return md_table(d.rename(columns=hdr))


def table_vi_top():
    v = pd.read_csv(TABLES / "table_vulnerability_index.csv").head(10)
    v = v.assign(vi=v.vi.map("{:.3f}".format),
                 p_top10_random_weights=(100 * v.p_top10_random_weights).round(0).astype(int),
                 mean_yield=v.mean_yield.map("{:.2f}".format),
                 monsoon_flood_mean=(100 * v.monsoon_flood_mean).map("{:.1f}".format),
                 flash_flood_mean=(100 * v.flash_flood_mean).map("{:.1f}".format),
                 hot_days_mean=v.hot_days_mean.map("{:.1f}".format))
    hh = R["vi"].get("spatial_robustness", {}).get("hh_share", {})
    v["hh_share"] = v.district.map(lambda d: f"{100 * hh.get(d, 0):.0f}")
    return md_table(v[["rank", "district", "vi", "mean_yield", "monsoon_flood_mean",
                       "flash_flood_mean", "hot_days_mean", "p_top10_random_weights", "cluster_005",
                       "hh_share"]].rename(columns={
        "rank": "Rank", "district": "District", "vi": "Index",
        "mean_yield": "Yield (t/ha)", "monsoon_flood_mean": "Monsoon flood (%)",
        "flash_flood_mean": "Flash flood (%)", "hot_days_mean": "Hot days",
        "p_top10_random_weights": "Top-10 share (%)", "cluster_005": "LISA",
        "hh_share": "HH share (%)"}))


def table_mk():
    t = pd.read_csv(TABLES / "table_mann_kendall.csv")
    t = t.assign(tau=t.tau.round(3), sen_slope=t.sen_slope.map(lambda x: f"{x:+.4f}"),
                 p=t.p.map(fmt_p))
    return md_table(t.rename(columns={"variable": "Series", "years": "Harvest years", "n": "n",
                                      "trend": "Trend", "tau": "Kendall's tau", "sen_slope": "Sen's slope (per year)",
                                      "p": "p (Hamed–Rao)"}))


def table_fe_ap():
    d = pd.read_csv(TABLES / "table_panel_fe_area_production.csv").fillna("")
    return md_table(d.rename(columns={k: k.replace("Production", "Prod.") for k in d.columns if k != "Variable"}))


def table_event():
    d = pd.read_csv(TABLES / "table_event_2017.csv").head(8)
    d = d.assign(**{c: d[c].map(lambda x: minus(f"{x:+.1f}") if "change" in c else f"{x:.1f}")
                    for c in d.columns if c != "district"})
    return md_table(d.rename(columns={"district": "District", "s1_flash_flood_pct": "Flash flood, Sentinel-1 (%)",
                                      "jrc_flash_flood_pct": "Flash flood, JRC (%)",
                                      "area_change_pct": "Harvested area (%)", "yield_change_pct": "Yield (%)",
                                      "production_change_pct": "Production (%)"}))


def table_moran():
    d = pd.read_csv(TABLES / "table_residual_moran.csv")
    d = d.assign(moran_i=d.moran_i.round(3), p_sim=d.p_sim.map(lambda x: f"{x:.4f}"),
                 p_fdr=d.p_fdr.map(lambda x: f"{x:.4f}"))
    return md_table(d.rename(columns={"harvest_year": "Harvest year", "moran_i": "Moran's I",
                                      "p_sim": "Pseudo p", "p_fdr": "FDR-adjusted p"}))


def table_software(exclude=()):
    from importlib.metadata import version
    import platform
    pk = [("Python", platform.python_version(), "Language"),
          ("duckdb", version("duckdb"), "Analytical warehouse (Gold layer)"),
          ("pandas", version("pandas"), "Data manipulation"), ("numpy", version("numpy"), "Numerics"),
          ("pyarrow", version("pyarrow"), "Parquet (Silver layer)"),
          ("camelot-py", version("camelot-py"), "BBS PDF table extraction"),
          ("earthengine-api", version("earthengine-api"), "MODIS, ERA5-Land, JRC, Sentinel-1 extraction"),
          ("geopandas", version("geopandas"), "Boundaries and maps"),
          ("libpysal", version("libpysal"), "Spatial weights"), ("esda", version("esda"), "Moran's I, LISA"),
          ("linearmodels", version("linearmodels"), "Fixed-effects panel models"),
          ("statsmodels", version("statsmodels"), "FDR correction"),
          ("pymannkendall", version("pymannkendall"), "Mann–Kendall tests"),
          ("scipy", version("scipy"), "Rank correlations"), ("matplotlib", version("matplotlib"), "Figures"),
          ("streamlit", version("streamlit"), "Dashboard"), ("plotly", version("plotly"), "Dashboard charts")]
    pk = [p for p in pk if p[0] not in exclude]
    return md_table(pd.DataFrame(pk, columns=["Package", "Version", "Role"]))


def table_region_checks():
    g = pd.read_csv(V2_BRONZE / "bbs" / "bbs_region_checks.csv")
    g = g[g.check.str.startswith("single")]
    rows = [{"Region row (2013 edition, 2012-13)": r.unit.replace(" [single-district region]", ""),
             "Area (ha)": f"{r.region_area_ha:,.0f}", "Production (t)": f"{r.region_production_t:,.0f}",
             "District row (2014 edition, 2012-13)": r.districts,
             "Area (ha) ": f"{r.compare_area_ha:,.0f}", "Production (t) ": f"{r.compare_production_t:,.0f}"}
            for r in g.itertuples()]
    return md_table(pd.DataFrame(rows))


def table_flood_agreement():
    cols = {}
    for kind in ["monsoon", "flash"]:
        a = R[f"flood_overlap_{kind}"]
        cols[f"{kind.capitalize()} flood fraction"] = {
            "Harvest years": a["years"].replace("-", "–"),
            "District-years (districts)": f"{a['n']} ({a['n_districts']})",
            "Pooled r (95 % CI)": f"{a['pearson_r']:.2f} ({a['pearson_r_ci'][0]:.2f}–{a['pearson_r_ci'][1]:.2f})",
            "District-mean r": f"{a['district_mean_r']:.2f}",
            "Within-district r": f"{a['within_district_r']:.2f}",
            "Bias (pp)": minus(f"{100 * a['bias']:+.2f}"), "MAE (pp)": f"{100 * a['mae']:.2f}",
            "RMSE (pp)": f"{100 * a['rmse']:.2f}"}
    return md_table(pd.DataFrame(cols).rename_axis("Statistic").reset_index())


def table_timings():
    t = TIMINGS
    rows = [(k, f"{v:.0f} s") for k, v in t["local_s"].items()]
    rows += [(f"{k} (per harvest year, uncached)", f"{v:.0f} s") for k, v in t["gee_s_per_year"].items()]
    return md_table(pd.DataFrame(rows, columns=["Step", "Run time"]))


TABLE_FUNCS = {"table_alignment": table_alignment, "table_bbs_checks": table_bbs_checks,
               "table_descriptives": table_descriptives, "table_fe": table_fe,
               "table_fe_ap": table_fe_ap, "table_event": table_event, "table_moran": table_moran,
               "table_software": table_software,
               "table_software_ems": lambda: table_software(exclude=("linearmodels", "pymannkendall")),
               "table_timings": table_timings, "table_vi_top": table_vi_top, "table_mk": table_mk,
               "table_region_checks": table_region_checks, "table_flood_agreement": table_flood_agreement,
               "table_coverage": lambda: table_coverage(), "table_matching": lambda: table_matching(),
               "table_validation": lambda: table_validation(), "table_failure_tests": lambda: table_failure_tests(),
               "table_fresh_setup": lambda: table_fresh_setup(),
               "table_comparison_classes": lambda: table_comparison_classes(),
               "table_bbs_flow": lambda: table_bbs_flow()}
_tf = V2 / "outputs" / "pipeline_timings.json"
TIMINGS = json.loads(_tf.read_text(encoding="utf-8")) if _tf.exists() else {}
def _hh_summary():
    sr = R["vi"].get("spatial_robustness")
    if not sr:
        return {}
    base = R["vi"]["hh_005"]
    other = {d: v for d, v in sr["hh_share"].items() if d not in base}
    top_other = max(other, key=other.get)
    return dict(n=len(base), min=100 * min(sr["hh_share"][d] for d in base),
                max=100 * max(sr["hh_share"][d] for d in base),
                fdr_min=100 * min(sr["hh_fdr_share"][d] for d in base),
                fdr_max=100 * max(sr["hh_fdr_share"][d] for d in base),
                other_name=top_other, other_max=100 * other[top_other], **sr)


HH = _hh_summary()
_code = [*(V2 / "src").glob("*.py"), V2 / "run_all.py", V2 / "dashboard_v2.py"]
CODE = dict(lines=sum(len(p.read_text(encoding="utf-8").splitlines()) for p in _code),
            kb=round(sum(p.stat().st_size for p in _code) / 1024),
            duckdb_mb=(V2 / "data" / "gold" / "bangladesh_agri_v2.duckdb").stat().st_size / 2**20)


# ── Evaluation evidence: s03b validation, failure tests, fresh-setup test ──
# Test results are tied to the Gold panel they were produced from; results
# from different data are flagged in the manuscript instead of being used
# silently.
PANEL_SHA = panel_sha256()
MATCH = pd.read_csv(TABLES / "table_district_matching.csv")
XWALK = pd.read_csv(V2 / "mappings" / "district_crosswalk.csv")
VAL = json.loads((V2 / "outputs" / "validation_summary.json").read_text(encoding="utf-8"))
VREP = pd.read_csv(V2 / "outputs" / "validation_report.csv")
STALE = []


def _failure_tests():
    f = V2 / "outputs" / "failure_tests" / "results.csv"
    if not f.exists():
        STALE.append("failure tests not run (python v2/tests/run_failure_tests.py)")
        return pd.DataFrame(columns=["test", "corruption", "expected", "observed", "diagnostic", "result"])
    ft = pd.read_csv(f).fillna("")
    m = re.search(r"\(([0-9a-f]{12})\)", " ".join(ft[ft.test == "clean_rerun"].observed))
    if not m or m.group(1) != PANEL_SHA[:12]:
        STALE.append("failure tests were run on different data (rerun python v2/tests/run_failure_tests.py)")
    return ft


def _fresh_setup():
    f = V2 / "docs" / "fresh_setup_summary.json"
    if not f.exists():
        STALE.append("fresh-setup test not run (python v2/tests/run_fresh_setup_test.py)")
        return {"environments": {}}
    fs = json.loads(f.read_text(encoding="utf-8"))
    if fs["reference_panel_sha256"] != PANEL_SHA:
        STALE.append("fresh-setup test was run on different data (rerun python v2/tests/run_fresh_setup_test.py)")
    return fs


FT = _failure_tests()
FS = _fresh_setup()
FSE = FS["environments"]


def _notebook_rebuild():
    f = V2 / "docs" / "notebook_rebuild_summary.json"
    if not f.exists():
        STALE.append("notebook 01 not run (v2/notebooks/01_Data_Engineering_Pipeline.ipynb)")
        return {}
    nb = json.loads(f.read_text(encoding="utf-8"))
    if nb.get("panel_sha256") != PANEL_SHA:
        STALE.append("notebook 01 was run on different data (rerun v2/notebooks/01_Data_Engineering_Pipeline.ipynb)")
    elif nb.get("identical") != nb.get("compared") or not nb.get("panel_identical"):
        STALE.append("notebook 01 did not reproduce every pipeline file and table")
    return nb


NBR = _notebook_rebuild()


def sci(x):
    """Number in scientific notation for the text, e.g. 3 × 10⁻¹⁶."""
    m, e = f"{x:.0e}".split("e")
    return f"{m} × 10{str(int(e)).translate(str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))}"
_corrupt = FT[FT.test != "clean_rerun"]
_cmp = next(iter(FSE.values()), {}).get("comparison", {})
EVS = dict(records=int(MATCH.Records.sum()), spellings=int(XWALK.source_name.nunique()),
           unmatched=int(MATCH.Unmatched.sum()), corrupt=len(_corrupt),
           corrupt_pass=int((_corrupt.result == "PASS").sum()),
           baseline=" ".join(FT[FT.test == "clean_rerun"].result) or "[not run]",
           envs=len(FSE), files=next(iter(FSE.values()), {}).get("files_compared", 0),
           kept=_cmp.get("kept in repository", 0), identical=_cmp.get("identical", 0),
           same=_cmp.get("same content", 0), runtime=_cmp.get("run time only", 0),
           all_envs_pass=bool(FSE) and all(r["run_all_exit"] == 0 and r["compare_exit"] == 0
                                           and r["panel_sha256_matches"] for r in FSE.values()))
if FSE and not EVS["all_envs_pass"]:
    STALE.append("the fresh-setup test did not pass in every environment")
if len(FT) and (FT.result != "PASS").any():
    STALE.append("not every failure test passed")


EVS["generated"] = EVS["files"] - EVS["kept"]
_keys = {re.sub(r"[^a-z]", "", str(n).lower()) for n in XWALK.source_name}
EVS["alias_used"] = sum(k in _keys for k in __import__("common").ALIASES)
EVS["alias_distinct"] = int(XWALK[XWALK.rule == "alias rule"].source_name.nunique())


def fs_env(env, key, default="[not run]"):
    return FSE.get(env, {}).get(key, default)


CLASS_RULES = [("identical", "SHA-256 of the two files equal"),
               ("same content", "DuckDB: every table equal value by value. Word: every document part equal, "
                                "ignoring the write times stored in the file container. Logs: equal after "
                                "removing the folder path"),
               ("run time only", "The only differences are measured run times (the run-time table and the "
                                 "sentence quoting the total run time)"),
               ("kept in repository", "Not generated by the pipeline; checked for presence only"),
               ("DIFFERENT", "Any other difference, or a missing file; the test fails")]


def _file_list(files):
    groups = {}
    for f in files:
        folder, name = f.rsplit("/", 1) if "/" in f else ("", f)
        groups.setdefault(folder, []).append(name)
    out = []
    for folder, names in groups.items():
        if len(names) > 3:
            kinds = "/".join(sorted({Path(n).suffix.lstrip(".") for n in names}))
            out.append(f"{folder}/ ({len(names)} {kinds} files)")
        else:
            out += [f"{folder}/{n}" if folder else n for n in names]
    return "; ".join(out)


def table_comparison_classes():
    """Table 6: the comparison classes, with the exact files that fell in each
    class in the final fresh-setup test (environment B)."""
    found = sorted((V2 / "docs").glob("fresh_setup_comparison_*.csv"))
    c = pd.read_csv(found[-1]) if found else pd.DataFrame(columns=["file", "status"])
    rows = []
    for cls, rule in CLASS_RULES:
        files = c[c.status == cls].file.tolist()
        rows.append({"Class": cls.capitalize(), "Rule": rule,
                     "Files in the final test": f"{len(files)}: {_file_list(files)}" if files else "0"})
    return md_table(pd.DataFrame(rows))


def bbs_accounting():
    """From BBS rows parsed in the yearbooks to district-years in the panel."""
    rows = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_rows_all.csv")
    dist = rows[(rows.row_type == "district") & rows.crop_year.notna()].drop_duplicates(
        ["book_year", "crop_year", "district"])
    final = pd.read_csv(V2_BRONZE / "bbs" / "bbs_boro_district_year.csv")
    diffs = pd.read_csv(V2_BRONZE / "bbs" / "bbs_edition_diffs.csv")
    eds = dist.groupby("crop_year").book_year.agg(["min", "max", "nunique"])
    two = eds[eds["nunique"] > 1].index
    tables = dist.groupby(["book_year", "crop_year"]).district.nunique()
    missing = {}
    for (b, cy), n in tables[tables < 64].items():
        absent = sorted(set(dist.district) - set(dist[(dist.book_year == b) & (dist.crop_year == cy)].district))
        missing.setdefault(int(b), []).append(absent)
    miss_txt = "; ".join(
        f"{', '.join(v[0]) if len(v[0]) <= 3 else f'{len(v[0])} districts'} in "
        f"{'both crop years' if len(v) == 2 else 'one crop year'} of the {b} edition" for b, v in missing.items())
    fails = dist[~dist.qc_pass]
    fail_txt = "; ".join(f"{int(b)} edition, crop year {cy}" for b, cy in
                         sorted(set(zip(fails.book_year, fails.crop_year))))
    region = rows[rows.raw_name.str.contains("single-district region", na=False)]
    from_region = final.merge(region[["district", "crop_year", "book_year"]],
                              on=["district", "crop_year", "book_year"])
    latest = final.crop_year.map(eds["max"])
    single = eds[eds["nunique"] == 1]
    return dict(tables=len(tables), possible=64 * len(tables), parsed=len(dist),
                not_parsed=64 * len(tables) - len(dist), missing=miss_txt, fail=len(fails), fail_where=fail_txt,
                accepted=int(dist.qc_pass.sum()), two_first=two.min(), two_last=two.max(), n_two=len(two),
                possible_pairs=64 * len(two),
                pairs=int((dist.groupby(["district", "crop_year"]).book_year.nunique() > 1).sum()),
                diff=len(diffs),
                max_diff=int((diffs.late_area - diffs.early_area).abs().max()) if len(diffs) else 0,
                diff_years=", ".join(sorted(diffs.crop_year.unique())),
                panel=len(final), earlier=int((final.book_year < latest).sum()),
                single=int(final.crop_year.isin(single.index).sum()),
                single_txt=", ".join(f"{cy} ({int(r['min'])} edition)" for cy, r in single.iterrows()),
                region=len(from_region))


ACC = bbs_accounting()


def table_bbs_flow():
    a = ACC
    rows = [("Edition–crop-year tables located", a["tables"], "14 editions, two crop years each"),
            ("District rows possible", f"{a['possible']:,}", "64 per table"),
            ("District rows parsed", f"{a['parsed']:,}", f"{a['not_parsed']} not parsed: {a['missing']}"),
            ("Rows failing a unit identity (excluded)", a["fail"], a["fail_where"] + "; yield identity"),
            ("Rows accepted", f"{a['accepted']:,}", ""),
            ("District-year pairs printed in two editions", a["possible_pairs"],
             f"crop years {a['two_first']} to {a['two_last']}, 64 districts each"),
            ("Pairs with a parsed row in both editions (compared)", a["pairs"],
             "compared on area (ha) and yield (t/ha)"),
            ("Compared pairs that differ", a["diff"], f"each by at most {a['max_diff']} ha of area"),
            ("District-years in the panel", a["panel"],
             "later edition used where both editions have an accepted row"),
            ("  from the earlier edition (later row missing or failed)", a["earlier"], ""),
            ("  from a crop year printed in one edition only", a["single"], a["single_txt"]),
            ("  from single-district region rows", a["region"],
             "2012 and 2013 editions; region-to-district equivalence verified on crop year 2012-13 "
             "against the 2014 edition")]
    return md_table(pd.DataFrame(rows, columns=["Step", "Count", "Notes"]))


def table_coverage():
    import duckdb
    from schema import COVERAGE, PRODUCTS
    p = duckdb.connect(str(V2 / "data" / "gold" / "bangladesh_agri_v2.duckdb"),
                       read_only=True).execute("SELECT * FROM fact_boro_panel").df()
    groups = [("Boro area, yield, production (BBS)", "bbs", "yield_t_ha", None),
              ("Peak-season NDVI (MODIS)", "ndvi", "ndvi_peak", None),
              ("Temperature, precipitation, hot days (ERA5-Land)", "climate", "tmean_c", None),
              ("Monsoon flood fraction, JRC", "jrc", "jrc_monsoon_flood", "jrc_monsoon_obs"),
              ("Flash flood fraction, JRC", "jrc", "jrc_flash_flood", "jrc_flash_obs"),
              ("Monsoon flood fraction, Sentinel-1", "s1", "s1_monsoon_flood", None),
              ("Flash flood fraction, Sentinel-1", "s1", "s1_flash_flood", None)]
    rows = []
    for label, src, var, obs in groups:
        s = p[["harvest_year", var]].dropna()
        a, b = COVERAGE.get(var, ("", s.harvest_year.min(), s.harvest_year.max()))[1:]
        avail = PRODUCTS[src]["available"]
        rows.append({"Variable": label, "Product availability": avail[0].upper() + avail[1:],
                     "Harvest years": f"{a}–{b}",
                     "District-years with values": f"{len(s)} of {64 * (b - a + 1)}",
                     "Valid observations, % of district area: mean (minimum)":
                         f"{100 * p[obs].mean():.1f} % ({100 * p[obs].min():.0f} %)" if obs else "–"})
    return md_table(pd.DataFrame(rows))


def table_matching():
    # one column per source, so that the table fits the page width
    m = MATCH.set_index("Source").T.astype(object)
    m.loc["Records"] = m.loc["Records"].map("{:,}".format)
    m = m.rename(index={"Normalised": "Normalised (case, spacing, punctuation)",
                        "Region row": "Verified single-district region row"})
    return md_table(m.rename_axis("Measure").reset_index())


CATEGORY_TEXT = {
    "structural": "Required columns present in every Bronze file; Gold columns and types match the data dictionary",
    "relational": "Keys unique and non-null; row counts; every district in dim_district; joins neither drop "
                  "nor multiply records; non-missing values preserved through the joins",
    "temporal": "Harvest-year rule; 15 consecutive seasons × 64 districts; each covariate present for exactly "
                "its declared years",
    "value": "BBS values present in every row; every variable within its declared range",
    "geographic": "Every source name maps to the gazetteer; alias rules used and non-colliding; GADM one-to-one; "
                  "all 64 districts in each source; valid polygons, CRS and area sums",
    "cross-source": "Unit identities; district sums against printed national totals and text totals; "
                    "agreement between editions; region rows; national yield",
    "lineage": "Edition and page recorded for every BBS value; SHA-256 of every source file and extract "
               "matches the manifest; every extract documented"}


def table_validation():
    rows = []
    for cat, txt in CATEGORY_TEXT.items():
        g = VREP[VREP.category == cat]
        rows.append({"Category": cat.capitalize(), "What is checked": txt, "Checks": len(g),
                     "PASS": int((g.status == "PASS").sum()), "INFO": int((g.status == "INFO").sum()),
                     "FAIL": int((g.status == "FAIL").sum())})
    return md_table(pd.DataFrame(rows))


def table_failure_tests():
    t = FT[FT.test != "clean_rerun"].copy()
    if t.empty:
        return "[failure tests not run]"
    t["test"] = t.test.str.replace("_", " ").str.capitalize()
    t["Expected"] = t.expected.str.replace("stops at s03_build_panel.py with ", "stop at s03, ", regex=False)
    t["Diagnostic"] = [d if d else o for d, o in zip(t.diagnostic, t.observed)]
    t["Diagnostic"] = t.Diagnostic.str.replace("; check the source and add the spelling to common.ALIASES", "",
                                               regex=False)
    t["Stage"] = t.stage.str.replace(r" \(.*\)", "", regex=True) if "stage" in t else ""
    t["Diagnostic"] = t.Diagnostic.map(lambda x: x if len(x) <= 230 else x[:x.rfind(";", 0, 230)] + "; …")
    t["Diagnostic"] = t.Diagnostic.str.replace(r"(?<![\w-])-(?=\d)", "−", regex=True)   # minus signs
    return md_table(t.rename(columns={"test": "Test", "corruption": "Change to the input copy", "result": "Result"})
                    [["Test", "Change to the input copy", "Expected", "Diagnostic", "Result"]])


def table_fresh_setup():
    if not FSE:
        return "[fresh-setup test not run]"
    cols = {}
    for env, r in FSE.items():
        c = r["comparison"]
        cols[f"Environment {env} ({r['requirements']})"] = {
            "Packages installed": r["packages"],
            "Packages differing from the lock file": len(r["packages_differing_from_lock"]),
            "Pipeline (run_all.py)": f"completed, {r['run_all_s']} s" if r["run_all_exit"] == 0 else "failed",
            "Validation report": ", ".join(f"{v} {k}" for k, v in r["validation"].items()),
            "Failure tests passed": r.get("failure_cases_passed", r.get("failure_tests_passed")),
            "Baseline run": "passed" if r.get("baseline", "PASS") == "PASS" else "failed",
            "Gold panel checksum": "equal" if r["panel_sha256_matches"] else "differs",
            "Files compared": r["files_compared"],
            "Identical": c.get("identical", 0), "Same content": c.get("same content", 0),
            "Run time only": c.get("run time only", 0), "Kept in the repository": c.get("kept in repository", 0),
            "Different": c.get("DIFFERENT", 0)}
    return md_table(pd.DataFrame(cols).rename_axis("Measure").reset_index())


# ── Author–year citations (Elsevier Harvard), used for the EMS manuscript ──
def _clean(s):
    import html
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()


def _family(a):
    fam = _clean(a["family"])
    # Registry names sometimes arrive in capitals (e.g. MORAN); organisations
    # (no given name, e.g. OECD, GADM) are left as written.
    return fam.title() if fam.isupper() and len(fam) > 3 and a.get("given") else fam


def _initials(given):
    def one(tok):
        if "." in tok:                                   # "A.S.M." -> A.S.M.
            return "".join(c + "." for c in re.findall(r"[^\W\d_]", tok) if c.isupper())
        if tok.isupper() and len(tok) <= 4:              # "SVK" -> S.V.K.
            return "".join(c + "." for c in tok)
        return tok[0] + "."
    out = []
    for tok in re.split(r"\s+", _clean(given)):
        if tok:
            out.append("-".join(one(t) for t in tok.split("-") if t))
    return "".join(out)


def _title(t):
    t = _clean(t).rstrip(".")
    return t.capitalize() if t.isupper() else t


def cite_label(e):
    au = e["authors"]
    if len(au) == 1:
        names = _family(au[0])
    elif len(au) == 2:
        names = f"{_family(au[0])} and {_family(au[1])}"
    else:
        names = f"{_family(au[0])} et al."
    return names, str(e["year"])


JOURNAL_NAMES = {"plos one": "PLOS ONE", "plos computational biology": "PLOS Computational Biology",
                 "environmental modelling &amp; software": "Environmental Modelling & Software"}


def _sort_key(name):
    """Alphabetical order ignoring accents (Mölder before Muñoz-Sabater)."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)).lower()


def harvard_entry(e):
    au = e["authors"]
    shown = au[:10]
    names = ", ".join(f"{_family(a)}, {_initials(a['given'])}" if a.get("given") else _family(a) for a in shown)
    if len(au) > 10:
        names += ", et al."
    title = _title(e["title"])
    s = f"{names}, {e['year']}. {title}" + ("" if title.endswith(("?", "!")) else ".")
    t = e.get("type", "")
    if t in ("journal-article", "proceedings-article", "paper-conference", "posted-content", "preprint"):
        cont = _clean(e.get("container")) or ("arXiv preprint" if "arxiv" in str(e.get("doi", "")).lower() else "")
        cont = JOURNAL_NAMES.get(cont.lower(), cont)
        if cont:
            s += f" In: {cont}" if t in ("proceedings-article", "paper-conference") else f" {cont}"
        if e.get("volume"):
            s += f" {e['volume']}"
            if e.get("issue"):
                s += f" ({e['issue']})"
        if e.get("pages"):
            s += f", {str(e['pages']).replace('-', '–')}"
        s += "."
    elif t in ("dataset", "report", "book", "software", "text"):
        if t == "dataset" and "[dataset]" not in s:
            s = s[:-1] + " [dataset]."
        if e.get("publisher"):
            s += f" {_clean(e['publisher'])}."
    else:
        cont = _clean(e.get("container"))
        if cont:
            s += f" {cont}."
    if e.get("doi"):
        s += f" https://doi.org/{e['doi']}"
    return s


def author_year(md, refs_path):
    refs = json.loads(refs_path.read_text(encoding="utf-8"))
    cited = []

    def lab(key):
        if key not in refs:
            raise KeyError(f"unknown citation key: {key}")
        if key not in cited:
            cited.append(key)
        return cite_label(refs[key])

    def paren(m):
        keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
        groups = []                          # same authors cited together: (BBS, 2013, 2026)
        for n, y in map(lab, keys):
            if groups and groups[-1][0] == n:
                groups[-1][1].append(y)
            else:
                groups.append((n, [y]))
        return "(" + "; ".join(f"{n}, {', '.join(ys)}" for n, ys in groups) + ")"

    md = re.sub(r"\[(@[\w-]+(?:\s*;\s*@[\w-]+)*)\]", paren, md)
    md = re.sub(r"(?<![\w.])@([a-z][\w-]*\d{4}[a-z]?)\b",
                lambda m: "{} ({})".format(*lab(m.group(1))) if m.group(1) in refs else m.group(0), md)
    # Disambiguation check: identical label+year for different keys
    seen = {}
    for k in cited:
        seen.setdefault(cite_label(refs[k]), []).append(k)
    clash = {k: v for k, v in seen.items() if len(v) > 1}
    assert not clash, f"ambiguous citations: {clash}"
    order = sorted(cited, key=lambda k: (_sort_key(_family(refs[k]["authors"][0])), str(refs[k]["year"])))
    reflist = "\n\n".join(harvard_entry(refs[k]) for k in order)
    unused = sorted(set(refs) - set(cited))
    if unused:
        print("note: references in references.json not cited:", unused)
    return md.replace("<<REFERENCES>>", reflist)


CONFIGS = {"paper": dict(out="Manuscript_v2", cite="numeric"),
           "paper_ems": dict(out="Manuscript_EMS", cite="author-year", abstract_max=150,
                             highlights=True)}


def render(text):
    def ev(m):
        expr = m.group(1).strip()
        if expr in TABLE_FUNCS:
            return TABLE_FUNCS[expr]()
        return str(eval(expr, {"R": R, "REG": REG, "AP": AP, "EX": EX, "BBS": BBS, "VI": VI, "TOP": TOP, "EV": EV, "DESC": DESC, "NATSUM": NATSUM, "T": TIMINGS, "CODE": CODE, "HH": HH, "GEO": GEO,
                               "MATCH": MATCH, "XWALK": XWALK, "VAL": VAL, "VREP": VREP, "FT": FT, "FS": FS,
                               "FSE": FSE, "CHP": CHP, "fs_env": fs_env, "EVS": EVS, "ACC": ACC, "NBR": NBR, "sci": sci, "MI": MATCH.set_index("Source"), "ALIASES": __import__("common").ALIASES, "int": int, "sum": sum, "coef": coef, "pct": pct,
                               "fmt_p": fmt_p, "p_eq": p_eq, "f": f, "w": w, "len": len, "round": round, "abs": abs,
                               "max": max, "min": min}))
    return re.sub(r"\{\{(.+?)\}\}", ev, text, flags=re.S)


def renumber_citations(md):
    """Number references in order of first citation and check coverage."""
    body, rest = md.split("# References", 1)
    refs, tail = rest.split("# Appendix", 1)
    order = []
    for grp in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", body):
        for n in (int(x) for x in grp.split(",")):
            if n not in order:
                order.append(n)
    entries = dict(re.findall(r"^\[(\d+)\] (.+)$", refs, flags=re.M))
    entries = {int(k): v for k, v in entries.items()}
    missing = set(order) - set(entries)
    uncited = set(entries) - set(order)
    assert not missing and not uncited, f"citations missing {missing}, uncited {uncited}"
    new = {old: i + 1 for i, old in enumerate(order)}
    body = re.sub(r"\[(\d+(?:\s*,\s*\d+)*)\]",
                  lambda m: "[" + ",".join(str(new[int(x)]) for x in m.group(1).split(",")) + "]", body)
    refs = "\n\n" + "\n\n".join(f"[{new[o]}] {entries[o]}" for o in order) + "\n\n"
    return body + "# References" + refs + "# Appendix" + tail


def pandoc(src, dst):
    cmd = ["pandoc", str(src), "-o", str(dst), "--resource-path", str(V2 / "outputs"),
           "--from", "markdown+pipe_tables", "--reference-doc", str(V2 / "paper" / "reference.docx")]
    subprocess.run(cmd, check=True)
    print("wrote", dst)


def main(paper="paper"):
    cfg = CONFIGS[paper]
    pdir = V2 / paper
    parts = sorted((pdir / "parts").glob("*.md"))
    md = "\n\n".join(render(p.read_text(encoding="utf-8")) for p in parts)
    if cfg["cite"] == "numeric":
        md = renumber_citations(md)
    else:
        md = author_year(md, pdir / "references.json")
    if cfg.get("abstract_max"):
        abstract = md.split("# Abstract", 1)[1].split("\n# ", 1)[0].split("Keywords:", 1)[0].rstrip().rstrip("*")
        n = len(re.findall(r"\S+", abstract))
        print(f"abstract: {n} words")
        assert n <= cfg["abstract_max"], f"abstract has {n} words (> {cfg['abstract_max']})"
    if STALE:
        print("WARNING: evaluation evidence out of date:", "; ".join(STALE))
        note = "**DRAFT: evaluation evidence out of date: " + "; ".join(STALE) + ".**\n\n"
        head, sep, body = md.partition("\n---\n") if md.startswith("---") else ("", "", md)
        md = head + sep + "\n" + note + body
    out_md = pdir / f"{cfg['out']}.md"
    out_md.write_text(md, encoding="utf-8")
    pandoc(out_md, pdir / f"{cfg['out']}.docx")
    if cfg.get("highlights"):
        hl = render((pdir / "highlights.md").read_text(encoding="utf-8"))
        for line in re.findall(r"^- (.+)$", hl, flags=re.M):
            assert len(line) <= 85, f"highlight over 85 characters ({len(line)}): {line}"
        # not "Highlights.md": on case-insensitive file systems that is the source file
        (pdir / "Highlights_rendered.md").write_text(hl, encoding="utf-8")
        pandoc(pdir / "Highlights_rendered.md", pdir / "Highlights.docx")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "paper")
