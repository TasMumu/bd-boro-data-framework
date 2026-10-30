"""Step 4 - Statistical analysis on the BBS-only panel (Gold layer).

1. Descriptive statistics
2. Two-way fixed-effects panel regressions (district + year effects),
   SEs clustered by district; Driscoll-Kraay SEs as a check for
   cross-sectional (spatial) correlation.
3. Spatial dependence in regression residuals (Moran's I per year).
4. Vulnerability index, weight sensitivity, global Moran's I and LISA.
5. Mann-Kendall trend tests (Hamed-Rao variance correction).

Every number quoted in the manuscript is written to v2/outputs/tables/ or
v2/outputs/results.json by this script.
"""
import json
import warnings

import duckdb
import esda
import geopandas as gpd
import libpysal
import numpy as np
import pandas as pd
import pymannkendall as mk
from linearmodels.panel import PanelOLS
from scipy import stats
from statsmodels.stats.multitest import multipletests

from common import BRONZE, TABLES, V2, V2_GOLD, canon_district

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(20260827)
R = {}                                       # results.json


def load():
    con = duckdb.connect(str(V2_GOLD), read_only=True)
    p = con.execute("SELECT * FROM fact_boro_panel").df()
    nat = con.execute("SELECT * FROM fact_boro_national ORDER BY harvest_year").df()
    con.close()
    # Rescaled regressors for readable coefficients
    p["log_area"] = np.log(p.area_ha)
    p["log_prod"] = np.log(p.production_t)
    p["ndvi_01"] = p.ndvi_peak * 10                  # per 0.1 NDVI
    p["precip_100"] = p.precip_mm / 100              # per 100 mm
    for c in ["jrc_monsoon_flood", "jrc_flash_flood", "s1_monsoon_flood", "s1_flash_flood"]:
        p[c.replace("_flood", "_10")] = p[c] * 10    # per 10 percentage points
    return p, nat


def weights():
    g = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_2.shp")
    g["district"] = g.NAME_2.map(canon_district)
    g = g.sort_values("district").reset_index(drop=True)
    # Fuzzy contiguity (100 m tolerance) avoids islands caused by slivers
    # between GADM polygons; row-standardised.
    gm = g.to_crs(32646)
    w = libpysal.weights.fuzzy_contiguity(gm, tolerance=0, buffering=True, buffer=100)
    w.transform = "r"
    R["weights"] = dict(n=w.n, islands=[g.district[i] for i in w.islands],
                        mean_neighbours=float(np.mean(list(w.cardinalities.values()))))
    return g, w


def flood_agreement(ov, j, s, n_boot=2000):
    """Agreement between JRC (j) and Sentinel-1 (s) fractions.  District-years
    are repeated observations of 64 districts, so the confidence interval for
    the pooled correlation resamples whole districts (cluster bootstrap), and
    correlations of district means and of within-district deviations are
    reported alongside."""
    diff = ov[s] - ov[j]
    dm = ov.groupby("district")[[j, s]].mean()
    within = ov[[j, s]] - ov.groupby("district")[[j, s]].transform("mean")
    rng = np.random.default_rng(20260827)
    dists = ov.district.unique()
    groups = {d: g for d, g in ov.groupby("district")}
    boot = []
    for _ in range(n_boot):
        b = pd.concat([groups[d] for d in rng.choice(dists, len(dists), replace=True)])
        boot.append(b[j].corr(b[s]))
    return dict(years=f"{ov.harvest_year.min()}-{ov.harvest_year.max()}", n=len(ov),
                n_districts=int(ov.district.nunique()),
                pearson_r=float(ov[j].corr(ov[s])),
                pearson_r_ci=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                spearman_r=float(ov[j].corr(ov[s], method="spearman")),
                district_mean_r=float(dm[j].corr(dm[s])),
                within_district_r=float(within[j].corr(within[s])),
                mean_jrc=float(ov[j].mean()), mean_s1=float(ov[s].mean()),
                bias=float(diff.mean()), mae=float(diff.abs().mean()),
                rmse=float(np.sqrt((diff ** 2).mean())))


# ── 1. Descriptives ──────────────────────────────────────────────────────
def descriptives(p):
    cols = {"yield_t_ha": "Boro yield (t/ha, husked rice)", "area_ha": "Boro area (ha)",
            "ndvi_peak": "Peak-season NDVI (Jan–Apr)", "tmean_c": "Mean temperature (°C)",
            "tmax_c": "Mean daily maximum temperature (°C)", "precip_mm": "Season precipitation (mm)",
            "hot_days": "Hot days, Tmax > 35 °C (Mar–May)",
            "jrc_monsoon_flood": "Monsoon flood fraction, JRC", "jrc_flash_flood": "Flash flood fraction, JRC",
            "s1_monsoon_flood": "Monsoon flood fraction, Sentinel-1", "s1_flash_flood": "Flash flood fraction, Sentinel-1"}
    rows = []
    for c, lab in cols.items():
        s = p[c].dropna()
        sub = p.loc[s.index]
        rows.append(dict(variable=lab, years=f"{sub.harvest_year.min()}-{sub.harvest_year.max()}",
                         n=len(s), mean=s.mean(), sd=s.std(), min=s.min(), max=s.max()))
    d = pd.DataFrame(rows)
    d.to_csv(TABLES / "table_descriptives.csv", index=False)
    R["n_panel"] = int(len(p)); R["n_districts"] = int(p.district.nunique())
    R["yield_mean"] = float(p.yield_t_ha.mean()); R["yield_sd"] = float(p.yield_t_ha.std())
    R["yield_min"] = float(p.yield_t_ha.min()); R["yield_max"] = float(p.yield_t_ha.max())
    R["yield_min_case"] = p.loc[p.yield_t_ha.idxmin(), ["district", "harvest_year"]].tolist()
    R["yield_max_case"] = p.loc[p.yield_t_ha.idxmax(), ["district", "harvest_year"]].tolist()
    # Agreement of the two flood sources where both exist
    rows = []
    for kind in ["monsoon", "flash"]:
        j, s = f"jrc_{kind}_flood", f"s1_{kind}_flood"
        R[f"flood_overlap_{kind}"] = a = flood_agreement(p.dropna(subset=[j, s]), j, s)
        rows.append({"Measure": f"{kind.capitalize()} flood", **a})
    pd.DataFrame(rows).to_csv(TABLES / "table_flood_agreement.csv", index=False)
    R["jrc_obs_min"] = float(p.jrc_monsoon_obs.min())
    return d


# ── 2. Panel regressions ─────────────────────────────────────────────────
LABELS = {"tmean_c": "Mean temperature (°C)", "precip_100": "Season precipitation (100 mm)",
          "hot_days": "Hot days (Tmax > 35 °C)", "ndvi_01": "Peak-season NDVI (0.1 units)",
          "jrc_monsoon_10": "Monsoon flood, JRC (10 pp)", "jrc_flash_10": "Flash flood, JRC (10 pp)",
          "s1_monsoon_10": "Monsoon flood, Sentinel-1 (10 pp)", "s1_flash_10": "Flash flood, Sentinel-1 (10 pp)"}
WEATHER = ["tmean_c", "precip_100", "hot_days"]
MODELS = {
    "M1": dict(x=WEATHER, years=(2011, 2025), title="Weather"),
    "M2": dict(x=WEATHER + ["ndvi_01"], years=(2011, 2025), title="Weather + NDVI"),
    "M3": dict(x=WEATHER + ["jrc_monsoon_10", "jrc_flash_10"], years=(2011, 2021), title="Weather + flood (JRC)"),
    "M4": dict(x=WEATHER + ["s1_monsoon_10", "s1_flash_10"], years=(2016, 2025), title="Weather + flood (Sentinel-1)"),
}


def fit(df, y, x, cov):
    d = df.set_index(["district", "harvest_year"])
    mod = PanelOLS(d[y], d[x], entity_effects=True, time_effects=True, drop_absorbed=True)
    if cov == "cluster":
        return mod.fit(cov_type="clustered", cluster_entity=True)
    return mod.fit(cov_type="kernel", kernel="bartlett", bandwidth=2)    # Driscoll-Kraay


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def run_model(p, y, spec):
    y0, y1 = spec["years"]
    df = p[p.harvest_year.between(y0, y1)].dropna(subset=[y] + spec["x"])
    rc, rd = fit(df, y, spec["x"], "cluster"), fit(df, y, spec["x"], "dk")
    out = dict(title=spec["title"], outcome=y, years=f"{y0}-{y1}", nobs=int(rc.nobs),
               n_districts=int(df.district.nunique()), r2=float(rc.rsquared),
               f_stat=float(rc.f_statistic_robust.stat), f_p=float(rc.f_statistic_robust.pval), coef={})
    for v in spec["x"]:
        out["coef"][v] = dict(b=float(rc.params[v]), se=float(rc.std_errors[v]), p=float(rc.pvalues[v]),
                              se_dk=float(rd.std_errors[v]), p_dk=float(rd.pvalues[v]))
    return df, rc, out


def pub_table(results, path, scale=1.0, dec=4):
    """Coefficient with stars (clustered p), (clustered SE) [Driscoll-Kraay p]."""
    rows = []
    for v, lab in LABELS.items():
        if not any(v in r["coef"] for r in results.values()):
            continue
        r1, r2 = {"Variable": lab}, {"Variable": ""}
        for m, r in results.items():
            c = r["coef"].get(v)
            r1[m] = f"{scale * c['b']:.{dec}f}{stars(c['p'])}" if c else ""
            r2[m] = f"({scale * c['se']:.{dec}f}) [{c['p_dk']:.3f}]" if c else ""
        rows += [r1, r2]
    for key, lab in [("years", "Harvest years"), ("n_districts", "Districts"), ("nobs", "Observations"),
                     ("r2", "R-squared (within, two-way)")]:
        rows.append({"Variable": lab, **{m: (f"{r[key]:.3f}" if key == "r2" else str(r[key]))
                                         for m, r in results.items()}})
    pd.DataFrame(rows).to_csv(path, index=False)


def regressions(p):
    # (a) Yield: four specifications
    out, res_store = {}, {}
    for m, spec in MODELS.items():
        df, rc, out[m] = run_model(p, "yield_t_ha", spec)
        res_store[m] = (df, rc)
    pub_table(out, TABLES / "table_panel_fe.csv")
    R["regressions"] = out
    # (b) Harvested area and production (log): BBS yield is measured per
    # harvested hectare, so crop destroyed before harvest lowers area and
    # production rather than yield.  Coefficients x100 = approx. % change.
    ap = {}
    for y, tag in [("log_area", "Area"), ("log_prod", "Production")]:
        for m in ["M1", "M3", "M4"]:
            _, _, ap[f"{tag} {m}"] = run_model(p, y, MODELS[m])
    pub_table(ap, TABLES / "table_panel_fe_area_production.csv", scale=100, dec=2)
    R["regressions_area_prod"] = ap
    # Sensitivity: is the Sentinel-1 flash-flood effect driven by 2017 alone?
    no17 = p[p.harvest_year != 2017]
    R["sensitivity_excl_2017"] = {f"{tag} M4": run_model(no17, y, MODELS["M4"])[2]
                                  for y, tag in [("log_area", "Area"), ("log_prod", "Production"),
                                                 ("yield_t_ha", "Yield")]}
    return res_store


# ── 3. Residual spatial dependence ───────────────────────────────────────
def residual_moran(res_store, g, w, model="M2"):
    df, r = res_store[model]
    resid = r.resids.reset_index()
    rows = []
    for yr, s in resid.groupby("harvest_year"):
        s = s.set_index("district").reindex(g.district)
        if s.iloc[:, -1].isna().any():
            continue
        np.random.seed(int(yr))                    # reproducible permutations
        mi = esda.Moran(s.iloc[:, -1].values, w, permutations=9999)
        rows.append(dict(harvest_year=int(yr), moran_i=mi.I, p_sim=mi.p_sim))
    d = pd.DataFrame(rows)
    d["p_fdr"] = multipletests(d.p_sim, method="fdr_bh")[1]
    d.to_csv(TABLES / "table_residual_moran.csv", index=False)
    R["residual_moran"] = dict(model=model, years=len(d), n_sig_005=int((d.p_sim < 0.05).sum()),
                               n_sig_fdr=int((d.p_fdr < 0.05).sum()),
                               median_I=float(d.moran_i.median()),
                               range_I=[float(d.moran_i.min()), float(d.moran_i.max())])
    return d


# ── 4. Vulnerability index ───────────────────────────────────────────────
COMPONENTS = {
    "low_yield": "Low mean yield (inverse of mean BBS yield, 2011-2025)",
    "production_instability": "Production instability (SD of detrended log BBS production, 2011-2025)",
    "monsoon_flood": "Monsoon flood exposure (mean JRC fraction, 2011-2021)",
    "flash_flood": "Flash flood exposure (mean JRC fraction, 2011-2021)",
    "heat": "Heat exposure (mean hot days, 2011-2025)",
}


def minmax(s):
    return (s - s.min()) / (s.max() - s.min())


def vulnerability(p, g, w):
    comp = {}
    for dn, d in p.groupby("district"):
        d = d.sort_values("harvest_year")
        # Production, not yield: crop lost before harvest leaves the BBS
        # harvested area and so does not lower reported yield.
        lp = np.log(d.production_t)
        slope, icpt = np.polyfit(d.harvest_year, lp, 1)
        resid = lp - (icpt + slope * d.harvest_year)
        dj = d[d.harvest_year <= 2021]
        comp[dn] = dict(mean_yield=d.yield_t_ha.mean(), prod_sd=resid.std(),
                        monsoon=dj.jrc_monsoon_flood.mean(), flash=dj.jrc_flash_flood.mean(),
                        hot=d.hot_days.mean())
    c = pd.DataFrame(comp).T.reindex(g.district)
    z = pd.DataFrame({"low_yield": minmax(-c.mean_yield), "production_instability": minmax(c.prod_sd),
                      "monsoon_flood": minmax(c.monsoon), "flash_flood": minmax(c.flash),
                      "heat": minmax(c.hot)})
    vi = z.mean(axis=1)
    rank = vi.rank(ascending=False, method="min").astype(int)
    top10 = set(rank[rank <= 10].index)

    # Weight sensitivity: (a) leave-one-component-out, (b) 10,000 random
    # weight vectors from a flat Dirichlet.
    loo = {}
    for k in z.columns:
        alt = z.drop(columns=k).mean(axis=1)
        alt_rank = alt.rank(ascending=False, method="min")
        loo[k] = dict(spearman=float(stats.spearmanr(vi, alt)[0]),
                      top10_overlap=len(top10 & set(alt_rank[alt_rank <= 10].index)))
    W = RNG.dirichlet(np.ones(z.shape[1]), 10000)
    sims = z.values @ W.T                                   # districts x draws
    sim_rank = (-sims).argsort(0).argsort(0) + 1
    p_top10 = (sim_rank <= 10).mean(1)
    rho = [stats.spearmanr(vi, sims[:, i])[0] for i in range(sims.shape[1])]

    np.random.seed(20260827)                       # reproducible permutations
    mi = esda.Moran(vi.values, w, permutations=9999)
    lisa = esda.Moran_Local(vi.values, w, permutations=9999, seed=1)
    q = pd.Series(lisa.q, index=vi.index).map({1: "HH", 2: "LH", 3: "LL", 4: "HL"})
    p_fdr = multipletests(lisa.p_sim, method="fdr_bh")[1]
    out = pd.DataFrame({"district": vi.index, "division": g.set_index("district").NAME_1.replace({"Barisal": "Barishal", "Chittagong": "Chattogram"}).reindex(vi.index).values,
                        **{k: z[k].values for k in z.columns},
                        "mean_yield": c.mean_yield.values, "prod_instability_sd": c.prod_sd.values,
                        "monsoon_flood_mean": c.monsoon.values, "flash_flood_mean": c.flash.values,
                        "hot_days_mean": c.hot.values,
                        "vi": vi.values, "rank": rank.values, "p_top10_random_weights": p_top10,
                        "lisa_q": q.values, "lisa_p": lisa.p_sim, "lisa_p_fdr": p_fdr})
    out["cluster_005"] = np.where(out.lisa_p < 0.05, out.lisa_q, "ns")
    out["cluster_fdr"] = np.where(out.lisa_p_fdr < 0.05, out.lisa_q, "ns")
    out = out.sort_values("rank")
    out.to_csv(TABLES / "table_vulnerability_index.csv", index=False)
    R["vi"] = dict(components=COMPONENTS, weights="equal (0.2 each)",
                   min=[out.district.iloc[-1], float(out.vi.iloc[-1])],
                   max=[out.district.iloc[0], float(out.vi.iloc[0])],
                   top10=out.district.head(10).tolist(),
                   robust_top10=out[out.p_top10_random_weights >= 0.5].district.tolist(),
                   leave_one_out=loo,
                   random_weights=dict(draws=10000, spearman_median=float(np.median(rho)),
                                       spearman_p05=float(np.percentile(rho, 5))),
                   moran_I=float(mi.I), moran_z=float(mi.z_sim), moran_p=float(mi.p_sim),
                   permutations=9999,
                   hh_005=out[out.cluster_005 == "HH"].district.tolist(),
                   ll_005=out[out.cluster_005 == "LL"].district.tolist(),
                   hh_fdr=out[out.cluster_fdr == "HH"].district.tolist(),
                   ll_fdr=out[out.cluster_fdr == "LL"].district.tolist(),
                   component_corr=z.corr().round(3).to_dict())
    # Validation of the JRC exposure component against Sentinel-1 means
    s1m = p[p.harvest_year >= 2016].groupby("district").s1_monsoon_flood.mean().reindex(vi.index)
    R["vi"]["jrc_vs_s1_district_mean_spearman"] = float(stats.spearmanr(c.monsoon, s1m)[0])
    R["vi"]["spatial_robustness"] = spatial_robustness(z, W, w)
    return out


def spatial_robustness(z, W, w, n_draws=1000, perms=999):
    """Recompute global Moran's I and LISA for the index under alternative
    weights (the first n_draws of the random weight vectors), so that the
    stability of the spatial cluster, not only of the ranking, is tested."""
    districts = z.index
    hh = np.zeros(len(districts))
    hh_fdr = np.zeros(len(districts))
    sig_global, moran_i = 0, []
    for k in range(n_draws):
        v = z.values @ W[k]
        np.random.seed(k)
        m = esda.Moran(v, w, permutations=perms)
        moran_i.append(m.I)
        sig_global += m.p_sim < 0.05
        loc = esda.Moran_Local(v, w, permutations=perms, seed=k)
        is_hh = loc.q == 1
        hh += is_hh & (loc.p_sim < 0.05)
        hh_fdr += is_hh & (multipletests(loc.p_sim, method="fdr_bh")[1] < 0.05)
    t = pd.DataFrame({"district": districts, "share_hh_005": hh / n_draws,
                      "share_hh_fdr": hh_fdr / n_draws}).sort_values("share_hh_005", ascending=False)
    t.to_csv(TABLES / "table_spatial_robustness.csv", index=False)
    return dict(draws=n_draws, permutations=perms,
                share_global_sig=float(sig_global / n_draws),
                moran_I_median=float(np.median(moran_i)),
                moran_I_p05=float(np.percentile(moran_i, 5)),
                moran_I_p95=float(np.percentile(moran_i, 95)),
                hh_share=t.set_index("district").share_hh_005.round(3).to_dict(),
                hh_fdr_share=t.set_index("district").share_hh_fdr.round(3).to_dict())


# ── 4b. Event check: the April 2017 haor flash flood ─────────────────────
def event_2017(p):
    base = p[p.harvest_year.isin([2015, 2016])].groupby("district")[["area_ha", "yield_t_ha", "production_t"]].mean()
    e = p[p.harvest_year == 2017].set_index("district")
    d = pd.DataFrame({
        "s1_flash_flood_pct": 100 * e.s1_flash_flood,
        "jrc_flash_flood_pct": 100 * e.jrc_flash_flood,
        "area_change_pct": 100 * (e.area_ha / base.area_ha - 1),
        "yield_change_pct": 100 * (e.yield_t_ha / base.yield_t_ha - 1),
        "production_change_pct": 100 * (e.production_t / base.production_t - 1)}).sort_values(
        "s1_flash_flood_pct", ascending=False)
    d.round(2).to_csv(TABLES / "table_event_2017.csv")
    R["event_2017"] = dict(
        top6=d.head(6).round(1).reset_index().to_dict("records"),
        spearman_s1_area=float(stats.spearmanr(d.s1_flash_flood_pct, d.area_change_pct)[0]),
        spearman_s1_area_p=float(stats.spearmanr(d.s1_flash_flood_pct, d.area_change_pct)[1]),
        spearman_s1_yield=float(stats.spearmanr(d.s1_flash_flood_pct, d.yield_change_pct)[0]),
        spearman_s1_yield_p=float(stats.spearmanr(d.s1_flash_flood_pct, d.yield_change_pct)[1]))
    return d


# ── 5. Trends ────────────────────────────────────────────────────────────
def trends(p, nat):
    rows = []
    w = p.groupby("harvest_year").apply(lambda d: pd.Series({
        "ndvi_peak": np.average(d.ndvi_peak.dropna(), weights=d.loc[d.ndvi_peak.notna(), "area_ha"]),
        "tmean_c": np.average(d.tmean_c, weights=d.area_ha),
        "precip_mm": np.average(d.precip_mm, weights=d.area_ha),
        "hot_days": np.average(d.hot_days, weights=d.area_ha)}))
    # National yield = sum of district production / sum of district area.
    # Where BBS prints a national row these agree with it (checked below).
    agg = p.groupby("harvest_year")[["production_t", "area_ha"]].sum()
    nat_yield = agg.production_t / agg.area_ha
    chk = nat.set_index("harvest_year").printed_national_yield_t_ha.dropna()
    R["national_yield_check_max_abs_diff"] = float((nat_yield.reindex(chk.index) - chk).abs().max())
    R["national_yield"] = {int(k): float(v) for k, v in nat_yield.items()}
    R["national_production"] = {int(k): float(v) for k, v in agg.production_t.items()}
    series = {"National Boro yield (t/ha, BBS)": nat_yield,
              "Peak-season NDVI (area-weighted)": w.ndvi_peak,
              "Mean temperature (°C, area-weighted)": w.tmean_c,
              "Season precipitation (mm, area-weighted)": w.precip_mm,
              "Hot days (area-weighted)": w.hot_days}
    for lab, s in series.items():
        s = s.sort_index()
        r = mk.hamed_rao_modification_test(s.values)
        rows.append(dict(variable=lab, years=f"{s.index.min()}-{s.index.max()}", n=len(s),
                         trend=r.trend, tau=r.Tau, sen_slope=r.slope, p=r.p))
    t = pd.DataFrame(rows)
    t.to_csv(TABLES / "table_mann_kendall.csv", index=False)
    w.join(nat_yield.rename("national_yield")).to_csv(
        TABLES / "national_annual_series.csv")
    # District-level yield trends with FDR control
    dr = []
    for dn, d in p.groupby("district"):
        r = mk.hamed_rao_modification_test(d.sort_values("harvest_year").yield_t_ha.values)
        dr.append(dict(district=dn, tau=r.Tau, sen_slope=r.slope, p=r.p))
    dr = pd.DataFrame(dr)
    dr["p_fdr"] = multipletests(dr.p, method="fdr_bh")[1]
    dr.to_csv(TABLES / "table_district_yield_trends.csv", index=False)
    R["trends"] = t.to_dict("records")
    R["district_trends"] = dict(n_up_fdr=int(((dr.p_fdr < 0.05) & (dr.sen_slope > 0)).sum()),
                                n_down_fdr=int(((dr.p_fdr < 0.05) & (dr.sen_slope < 0)).sum()),
                                median_slope=float(dr.sen_slope.median()))
    return t


def main():
    p, nat = load()
    g, w = weights()
    descriptives(p)
    res = regressions(p)
    residual_moran(res, g, w)
    vulnerability(p, g, w)
    event_2017(p)
    trends(p, nat)
    (V2 / "outputs" / "results.json").write_text(json.dumps(R, indent=2, default=float), encoding="utf-8")
    print(json.dumps(R, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
