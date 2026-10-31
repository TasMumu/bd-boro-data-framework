# Bangladesh Boro Rice Vulnerability Dashboard (v2, BBS-observed data only)
# 64 districts · Boro harvest years 2011–2025
# Author: Tasnim Ahmad Mumu
# Run: streamlit run v2/dashboard_v2.py
# Every figure shown is read from the v2 Gold layer or v2/outputs; nothing
# is hard-coded.
# ═══════════════════════════════════════════════════════════════════

import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st

V2 = Path(__file__).parent
ROOT = V2.parent
GOLD = V2 / "data" / "gold" / "bangladesh_agri_v2.duckdb"
TABLES = V2 / "outputs" / "tables"
RESULTS = V2 / "outputs" / "results.json"

# GADM v4.1 boundaries are not redistributed with the code (licence). Locally the pipeline's
# downloaded shapefile is used; on a deployed app (e.g. Streamlit Cloud) the district layer is
# downloaded once from GADM and cached in the temporary folder.
GADM_SHP = ROOT / "data" / "bronze" / "gadm_shapefiles" / "gadm41_BGD_2.shp"
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_BGD_2.json.zip"

st.set_page_config(page_title="Bangladesh Boro Vulnerability", page_icon="🌾", layout="wide")
st.markdown("""
<style>
[data-testid="stMetric"] { border: 1px solid rgba(100,116,139,0.25); border-radius: 10px;
                           padding: 14px 18px; background: rgba(34,197,94,0.04); }
[data-testid="stMetricLabel"] { font-size: 0.72rem !important; font-weight: 700 !important;
                                text-transform: uppercase !important; color: #22c55e !important; }
h1 { border-left: 4px solid #22c55e; padding-left: 14px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load():
    con = duckdb.connect(str(GOLD), read_only=True)
    panel = con.execute("SELECT * FROM fact_boro_panel").df()
    national = con.execute("SELECT * FROM fact_boro_national ORDER BY harvest_year").df()
    con.close()
    vi = pd.read_csv(TABLES / "table_vulnerability_index.csv")
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    return panel, national, vi, res


def gadm_districts():
    # Path to the GADM v4.1 district layer: the local shapefile if present, else a cached download
    if GADM_SHP.exists():
        return GADM_SHP
    cached = Path(tempfile.gettempdir()) / "gadm41_BGD_2.json"
    if not cached.exists():
        zpath = cached.with_suffix(".json.zip")
        with urllib.request.urlopen(GADM_URL, timeout=120) as r, open(zpath, "wb") as f:
            f.write(r.read())
        with zipfile.ZipFile(zpath) as z:
            member = next(n for n in z.namelist() if n.endswith(".json"))
            with z.open(member) as src, open(cached, "wb") as dst:
                dst.write(src.read())
        zpath.unlink(missing_ok=True)
    return cached


@st.cache_data(show_spinner="Loading district boundaries (GADM v4.1) ...")
def load_geo():
    import sys
    sys.path.insert(0, str(V2 / "src"))
    from common import canon_district
    g = gpd.read_file(gadm_districts())
    g["district"] = g.NAME_2.map(canon_district)
    if g.district.isna().any() or g.district.nunique() != 64:
        raise ValueError(f"GADM names not mapped to the 64 districts: {sorted(g.NAME_2[g.district.isna()])}")
    g["geometry"] = g.geometry.simplify(0.005)
    return g[["district", "geometry"]]


panel, national, vi, res = load()
try:
    geo = load_geo()                      # an exception is not cached, so the next rerun tries again
    geo_error = None
except Exception as e:                    # maps are optional: the rest of the dashboard still works
    geo, geo_error = None, f"{type(e).__name__}: {e}"
years = f"{panel.harvest_year.min()}–{panel.harvest_year.max()}"

page = st.sidebar.radio("Navigate", ["Overview", "District explorer", "Vulnerability & clusters",
                                     "Data quality"])
st.sidebar.caption("Data: BBS Yearbooks of Agricultural Statistics (2012–2025 editions), "
                   "MODIS, ERA5-Land, JRC GSW, Sentinel-1. No imputed or proxy values.")

if page == "Overview":
    st.title("Boro Rice Vulnerability — Overview")
    c = st.columns(5)
    c[0].metric("Districts", panel.district.nunique())
    c[1].metric("Harvest years", f"{panel.harvest_year.min()}–{str(panel.harvest_year.max())[2:]}")
    c[2].metric("District-years", len(panel))
    c[3].metric(f"Yield {national.harvest_year.iloc[-1]} (t/ha)", f"{national.yield_t_ha.iloc[-1]:.3f}")
    c[4].metric("Moran's I", f"{res['vi']['moran_I']:.3f}")
    st.caption(f"Moran's I of the vulnerability index, pseudo p = {res['vi']['moran_p']:.4f} "
               f"({res['vi']['permutations']:,} permutations). All yields are BBS-observed.")
    st.plotly_chart(px.line(national, x="harvest_year", y="yield_t_ha", markers=True,
                            labels={"harvest_year": "Boro harvest year", "yield_t_ha": "t/ha (husked rice)"},
                            title="National Boro yield (BBS)"), use_container_width=True)

elif page == "District explorer":
    st.title("District explorer")
    d = st.selectbox("District", sorted(panel.district.unique()))
    dp = panel[panel.district == d].sort_values("harvest_year")
    var = st.selectbox("Variable", ["yield_t_ha", "area_ha", "ndvi_peak", "tmean_c", "precip_mm",
                                    "hot_days", "jrc_monsoon_flood", "s1_monsoon_flood",
                                    "jrc_flash_flood", "s1_flash_flood"])
    st.plotly_chart(px.line(dp, x="harvest_year", y=var, markers=True), use_container_width=True)
    st.dataframe(dp.set_index("harvest_year"), use_container_width=True)

elif page == "Vulnerability & clusters":
    st.title("Vulnerability index and spatial clusters")
    if geo is None:
        st.warning("District boundaries could not be loaded, so the maps are not shown. "
                   f"({geo_error})")
        st.dataframe(vi[["rank", "district", "division", "vi", "p_top10_random_weights", "cluster_005"]],
                     use_container_width=True, hide_index=True)
        st.stop()
    g = geo.merge(vi, on="district").set_index("district")
    t1, t2 = st.tabs(["Index", "LISA clusters"])
    with t1:
        fig = px.choropleth(g, geojson=g.geometry, locations=g.index, color="vi",
                            color_continuous_scale="YlOrRd", hover_data=["rank", "p_top10_random_weights"])
        fig.update_geos(fitbounds="locations", visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vi[["rank", "district", "division", "vi", "p_top10_random_weights"]],
                     use_container_width=True, hide_index=True)
    with t2:
        fig = px.choropleth(g, geojson=g.geometry, locations=g.index, color="cluster_005",
                            color_discrete_map={"HH": "#b91c1c", "LL": "#15803d", "HL": "#f59e0b",
                                                "LH": "#60a5fa", "ns": "#e5e7eb"})
        fig.update_geos(fitbounds="locations", visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Clusters at pseudo p < 0.05 (9,999 permutations). "
                   f"Surviving FDR correction: HH {res['vi']['hh_fdr']}, LL {res['vi']['ll_fdr']}.")
    st.caption("District boundaries: GADM v4.1 (gadm.org), downloaded from GADM; not redistributed.")

else:
    st.title("Data quality")
    st.subheader("BBS extraction checks (district sum vs printed national total)")
    st.dataframe(pd.read_csv(V2 / "data" / "bronze" / "bbs" / "bbs_edition_checks.csv"),
                 use_container_width=True, hide_index=True)
    st.subheader("Non-missing observations per variable and year")
    cov = panel.groupby("harvest_year").apply(lambda d: d.notna().sum()).drop(
        columns=["district", "harvest_year"], errors="ignore")
    st.dataframe(cov, use_container_width=True)
