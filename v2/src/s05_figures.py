"""Step 5 - Manuscript figures (300 dpi PNG) from Gold tables and step-4 outputs."""
import json

import duckdb
import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Patch

from common import BRONZE, FIGURES, TABLES, V2, V2_GOLD, canon_district

matplotlib.use("Agg")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
INK, MUTED, ACCENT, ACCENT2 = "#1f2937", "#6b7280", "#b45309", "#1d4ed8"
R = json.loads((V2 / "outputs" / "results.json").read_text(encoding="utf-8"))


def gold(sql):
    con = duckdb.connect(str(V2_GOLD), read_only=True)
    df = con.execute(sql).df()
    con.close()
    return df


def districts():
    g = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_2.shp")
    g["district"] = g.NAME_2.map(canon_district)
    return g


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    ax.set_xlim(0, 100); ax.set_ylim(0, 50); ax.axis("off")
    W, GAP = 22, 3.3
    cols = [("Sources", ["BBS Yearbooks 2012–2025", "MODIS MOD13Q1 v061", "ERA5-Land daily",
                         "JRC GSW v1.4 monthly", "Sentinel-1 GRD", "GADM, WorldCover, SRTM"]),
            ("Bronze", ["Unmodified PDFs", "camelot extraction", "Earth Engine extracts",
                        "Cached per variable-year"]),
            ("Silver", ["64-district gazetteer", "Arithmetic checks", "National-total checks",
                        "Edition comparison", "Range validation", "Harvest-year keys"]),
            ("Gold (DuckDB)", ["fact_boro_panel (960)", "fact_boro_national", "dim_district",
                               "stg_* source tables", "→ analysis, dashboard"])]
    for k, (title, items) in enumerate(cols):
        x = 1 + k * (W + GAP)
        h = 7 + 5 * len(items)
        ax.add_patch(FancyBboxPatch((x, 46 - h), W, h, boxstyle="round,pad=0.4",
                                    fc="#f3f4f6", ec=MUTED, lw=0.8))
        ax.text(x + W / 2, 43, title, ha="center", weight="bold", color=INK, fontsize=8.5)
        for i, it in enumerate(items):
            ax.text(x + 1.2, 37.5 - 5 * i, it, fontsize=6.6, color=INK, va="center")
        if k < 3:
            ax.annotate("", xy=(x + W + GAP - 0.4, 30), xytext=(x + W + 0.6, 30),
                        arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.4))
    fig.savefig(FIGURES / "fig1_pipeline.png"); plt.close(fig)


def fig_coverage():
    p = gold("SELECT * FROM fact_boro_panel")
    vars_ = {"yield_t_ha": "BBS yield", "ndvi_peak": "NDVI", "tmean_c": "ERA5-Land",
             "jrc_monsoon_flood": "Monsoon flood (JRC)", "jrc_flash_flood": "Flash flood (JRC)",
             "s1_monsoon_flood": "Monsoon flood (S1)", "s1_flash_flood": "Flash flood (S1)"}
    m = np.array([[p[p.harvest_year == y][v].notna().mean() for y in range(2011, 2026)] for v in vars_])
    fig, ax = plt.subplots(figsize=(7, 2.6))
    ax.imshow(m, cmap="Greys", vmin=0, vmax=1.4, aspect="auto")
    ax.set_yticks(range(len(vars_)), vars_.values())
    ax.set_xticks(range(15), range(2011, 2026), rotation=45)
    ax.set_xlabel("Boro harvest year")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, f"{m[i, j] * 64:.0f}" if m[i, j] else "", ha="center", va="center",
                    fontsize=6, color="white" if m[i, j] > 0.5 else INK)
    ax.spines[:].set_visible(False)
    fig.savefig(FIGURES / "fig2_coverage.png"); plt.close(fig)


def fig_maps():
    g = districts().merge(pd.read_csv(TABLES / "table_vulnerability_index.csv"), on="district")
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 4.4))
    g.plot("vi", ax=axs[0], cmap="YlOrRd", edgecolor="white", linewidth=0.3, legend=True,
           legend_kwds=dict(shrink=0.6, label="Vulnerability index"))
    import matplotlib.patheffects as pe
    # Patuakhali (2) and Barguna (4) are small neighbouring districts: their
    # labels are moved into the sea with leader lines so both stay legible.
    offsets = {"Patuakhali": (16, -14), "Barguna": (-16, -16)}
    for _, r in g[g["rank"] <= 5].iterrows():         # rank numbers; names in caption
        c = r.geometry.representative_point()
        dx, dy = offsets.get(r["district"], (0, 0))
        axs[0].annotate(str(r["rank"]), (c.x, c.y), xytext=(dx, dy), textcoords="offset points",
                        fontsize=7.5, ha="center", va="center", color=INK, weight="bold",
                        path_effects=[pe.withStroke(linewidth=2.2, foreground="white")],
                        arrowprops=dict(arrowstyle="-", color=INK, lw=0.6, shrinkA=4, shrinkB=0)
                        if (dx or dy) else None)
    colors = {"HH": "#b91c1c", "LL": "#15803d", "HL": "#f59e0b", "LH": "#60a5fa", "ns": "#e5e7eb"}
    g.plot(color=g.cluster_005.map(colors), ax=axs[1], edgecolor="white", linewidth=0.3)
    sig_fdr = g[g.cluster_fdr != "ns"]
    if len(sig_fdr):
        sig_fdr.boundary.plot(ax=axs[1], color=INK, linewidth=0.9)
    axs[1].legend(handles=[Patch(color=colors[k], label=k) for k in ["HH", "LL", "HL", "LH", "ns"]]
                  + [Patch(fc="none", ec=INK, label="FDR < 0.05")], loc="lower left", fontsize=6, frameon=False)
    for a, t in zip(axs, ["(a) Vulnerability index (top five numbered)", "(b) LISA clusters (p < 0.05)"]):
        a.set_title(t, fontsize=9, loc="left", y=1.0); a.axis("off")
    fig.savefig(FIGURES / "fig3_vulnerability_lisa.png"); plt.close(fig)


def fig_coefficients():
    labels = {"tmean_c": "Mean temperature (1 °C)", "precip_100": "Season precipitation (100 mm)",
              "hot_days": "Hot days (1 day)", "ndvi_01": "Peak NDVI (0.1)",
              "jrc_monsoon_10": "Monsoon flood, JRC (10 pp)", "jrc_flash_10": "Flash flood, JRC (10 pp)",
              "s1_monsoon_10": "Monsoon flood, S1 (10 pp)", "s1_flash_10": "Flash flood, S1 (10 pp)"}
    rows = []
    for m, r in R["regressions"].items():
        for v, c in r["coef"].items():
            rows.append(dict(model=m, var=v, b=c["b"], se=c["se"]))
    d = pd.DataFrame(rows)
    order = [v for v in labels if v in set(d["var"])]
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 4), gridspec_kw=dict(width_ratios=[1.15, 1]))
    ax = axs[0]
    offs = {"M1": -0.27, "M2": -0.09, "M3": 0.09, "M4": 0.27}
    cols = {"M1": MUTED, "M2": INK, "M3": ACCENT, "M4": ACCENT2}
    for m, dm in d.groupby("model"):
        y = [order.index(v) + offs[m] for v in dm["var"]]
        ax.errorbar(dm.b, y, xerr=1.96 * dm.se, fmt="o", ms=3.5, color=cols[m], capsize=2,
                    lw=1, label=f"{m}: {R['regressions'][m]['title']} ({R['regressions'][m]['years']})")
    ax.axvline(0, color=MUTED, lw=0.8, ls="--")
    ax.set_yticks(range(len(order)), [labels[v] for v in order]); ax.invert_yaxis()
    ax.set_xlabel("Effect on yield (t/ha), 95% CI")
    ax.set_title("(a) Yield", fontsize=9, loc="left")
    ax.legend(fontsize=5.8, frameon=False, loc="lower left", bbox_to_anchor=(0, -0.42))

    # (b) Flood effects on harvested area and production (% per 10 pp)
    ax = axs[1]
    fl = ["jrc_monsoon_10", "jrc_flash_10", "s1_monsoon_10", "s1_flash_10"]
    ap = R["regressions_area_prod"]
    for k, (tag, col, off) in enumerate([("Area", ACCENT, -0.12), ("Production", INK, 0.12)]):
        for i, v in enumerate(fl):
            m = "M3" if v.startswith("jrc") else "M4"
            c = ap[f"{tag} {m}"]["coef"][v]
            ax.errorbar(100 * c["b"], i + off, xerr=196 * c["se"], fmt="o", ms=3.5, color=col,
                        capsize=2, lw=1, label=f"log {tag.lower()}" if i == 0 else None)
    ax.axvline(0, color=MUTED, lw=0.8, ls="--")
    ax.set_yticks(range(len(fl)), [labels[v] for v in fl]); ax.invert_yaxis()
    ax.set_xlabel("Effect (%), 95% CI")
    ax.set_title("(b) Harvested area and production", fontsize=9, loc="left")
    ax.legend(fontsize=6.5, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES / "fig4_coefficients.png"); plt.close(fig)


def fig_trends():
    s = pd.read_csv(TABLES / "national_annual_series.csv", index_col=0)
    t = pd.read_csv(TABLES / "table_mann_kendall.csv").set_index("variable")
    panels = [("national_yield", "National Boro yield (t/ha)", "National Boro yield (t/ha, BBS)"),
              ("ndvi_peak", "Peak-season NDVI", "Peak-season NDVI (area-weighted)"),
              ("tmean_c", "Mean temperature (°C)", "Mean temperature (°C, area-weighted)"),
              ("hot_days", "Hot days, Tmax > 35 °C", "Hot days (area-weighted)")]
    fig, axs = plt.subplots(2, 2, figsize=(7, 4.6))
    for a, (c, lab, key) in zip(axs.ravel(), panels):
        a.plot(s.index, s[c], "o-", color=INK, ms=3, lw=1)
        r = t.loc[key]
        x = s.index.values
        a.plot(x, np.median(s[c] - r.sen_slope * x) + r.sen_slope * x, color=ACCENT, lw=1.2)
        ptxt = "p < 0.001" if r.p < 0.001 else f"p = {r.p:.3f}"
        a.set_title(f"{lab}\nSen slope {r.sen_slope:+.4f}/yr, {ptxt}", fontsize=8, loc="left")
        a.set_xticks(range(2011, 2026, 2))
    fig.tight_layout(); fig.savefig(FIGURES / "fig5_trends.png"); plt.close(fig)


def fig_flood_agreement():
    p = gold("SELECT * FROM fact_boro_panel")
    fig, axs = plt.subplots(1, 2, figsize=(7, 3.2))
    for a, (j, s, lab, key) in zip(axs, [("jrc_monsoon_flood", "s1_monsoon_flood", "Monsoon flood", "flood_overlap_monsoon"),
                                         ("jrc_flash_flood", "s1_flash_flood", "Flash flood", "flood_overlap_flash")]):
        d = p.dropna(subset=[j, s])
        a.scatter(d[j], d[s], s=6, alpha=0.5, color=INK)
        lim = max(d[j].max(), d[s].max()) * 1.05
        a.plot([0, lim], [0, lim], color=MUTED, ls="--", lw=0.8)
        o = R[key]
        a.set_title(f"{lab}, {o['years'].replace('-', '–')} (n = {o['n']})\nPearson r = {o['pearson_r']:.2f}", fontsize=8, loc="left")
        a.set_xlabel("JRC (Landsat) fraction"); a.set_ylabel("Sentinel-1 fraction")
    fig.tight_layout(); fig.savefig(FIGURES / "fig6_flood_agreement.png"); plt.close(fig)


def fig_lineage():
    """Data lineage as implemented: files and tables actually written by each
    step, with counts read from the outputs. Drawn at print size (6.9 in wide,
    7.2 pt text) so that it stays legible at the journal's text width."""
    import textwrap
    man = pd.read_csv(V2 / "data" / "bronze" / "manifest.csv")
    val = json.loads((V2 / "outputs" / "validation_summary.json").read_text(encoding="utf-8"))
    n_ext = int((man.kind == "Earth Engine extract").sum())
    n_pdf = int((man.kind == "BBS yearbook PDF").sum())
    n_rows = gold("SELECT count(*) AS n FROM fact_boro_panel").n.iloc[0]
    n_alias = len(__import__("common").ALIASES)

    W, FS, LINE = 18.2, 7.2, 1.6
    X = {"src": 0.0, "brz": 20.4, "slv": 40.8, "gld": 61.2, "out": 81.6}
    fig = plt.figure(figsize=(6.9, 5.0))
    ax = fig.add_axes([0, 0, 1, 1])                   # no margins: units map to the full width
    ax.set_xlim(-0.5, 100.5); ax.set_ylim(30, 96); ax.axis("off")
    for k, t in [("src", "Sources"), ("brz", "Bronze\ns01, s02, s02b"), ("slv", "Silver\ns03"),
                 ("gld", "Gold (DuckDB)\ns03"), ("out", "Checks and\noutputs")]:
        ax.text(X[k] + W / 2, 95.5, t, ha="center", va="top", weight="bold", fontsize=8, color=INK,
                linespacing=1.1)

    def box(col, top, text, fc="#f3f4f6"):
        x, h = X[col], LINE * (text.count("\n") + 1) + LINE
        y = top - h
        ax.add_patch(FancyBboxPatch((x, y), W, h, boxstyle="round,pad=0.25", fc=fc, ec=MUTED, lw=0.6))
        ax.text(x + 0.8, y + h / 2, text, fontsize=FS, va="center", color=INK, linespacing=1.15)
        return (x, y, h)

    def right(b, frac=0.5):
        return (b[0] + W + 0.3, b[1] + b[2] * frac)

    def left(b, frac=0.5):
        return (b[0] - 0.3, b[1] + b[2] * frac)

    def arrow(p, q):
        ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=0.7,
                                                        mutation_scale=7, shrinkA=0, shrinkB=0))

    def down(a, b):
        arrow((a[0] + W / 2, a[1] - 0.3), (b[0] + W / 2, b[1] + b[2] + 0.3))

    s_bbs = box("src", 90, f"BBS Yearbooks,\n{n_pdf} editions (PDF,\n2012–2025)")
    s_mod = box("src", 81, "MODIS MOD13Q1 v061\n+ WorldCover v200\ncropland mask")
    s_era = box("src", 72, "ERA5-Land daily")
    s_jrc = box("src", 66, "JRC GSW v1.4\nmonthly history")
    s_s1 = box("src", 58.6, "Sentinel-1 GRD (VV)\n+ SRTM slope mask")
    s_gadm = box("src", 51.2, "GADM v4.1 districts\n(polygons, GID_2)")

    b_rows = box("brz", 90, "Parsed BBS rows\n(bbs_boro_rows_all)\nwith QC flags")
    b_bbs = box("brz", 81, "BBS district-years\nwith edition and\npage (one row per\ndistrict-year)")
    b_gee = box("brz", 70.4, f"{n_ext} Earth Engine\nextracts, one per\nvariable and year:\n"
                             "district means over\nharvest-year\nwindows; checked\nfor completeness")
    b_man = box("brz", 55, "manifest.csv:\nSHA-256, product\nversions and date\nwindows of every\n"
                           "file and extract")

    v_con = box("slv", 86, "Input contract\n[SCHEMA] [MISSING]")
    v_har = box("slv", 78.6, f"District\nharmonisation:\n{n_alias} alias rules\n[DISTRICT]")
    v_sil = box("slv", 68, "One Parquet table\nper source, keyed\non district and\nharvest year\n"
                           "[KEY] [RANGE]")

    g_stg = box("gld", 76, "stg_* tables (5)\nand dim_district\n(64, GADM GID_2)")
    g_pan = box("gld", 65.6, f"fact_boro_panel\n({n_rows} rows), key:\ndistrict_id +\nharvest_year")
    g_nat = box("gld", 53.6, "fact_boro_national\n(15 rows)")

    o_val = box("out", 82, f"s03b validation\nreport: {val['checks']}\nchecks, "
                           f"{val['by_status'].get('FAIL', 0)} FAIL;\ncrosswalk, data\ndictionary", fc="#fef3c7")
    o_ana = box("out", 69.6, "s04–s05 analysis\ntables, figures")
    o_ms = box("out", 61.8, "s06 manuscript\n(numbers read\nfrom outputs)")
    o_das = box("out", 52.4, "Dashboard")

    arrow(right(s_bbs), left(b_rows))
    down(b_rows, b_bbs)
    for s, f in [(s_mod, 0.9), (s_era, 0.7), (s_jrc, 0.45), (s_s1, 0.2)]:
        arrow(right(s), left(b_gee, f))
    arrow(right(s_gadm), left(b_gee, 0.05))
    arrow(right(b_bbs, 0.6), left(v_con, 0.3))
    arrow(right(b_gee, 0.9), left(v_con, 0.1))
    down(v_con, v_har)
    down(v_har, v_sil)
    arrow(right(v_sil, 0.7), left(g_stg, 0.3))
    down(g_stg, g_pan)
    down(g_pan, g_nat)
    for o in (o_val, o_ana, o_ms, o_das):
        arrow(right(g_pan), left(o))

    notes = [("Validation stages: s01 excludes rows that fail a unit identity, stops if a row's crop years do not "
              "match the table header, a district appears twice in a table or a region row does not reconcile, and "
              "computes district sums and edition differences → s02 extract completeness → s03 input "
              "contract, gazetteer, keys, ranges and panel completeness (check IDs in brackets; stop on failure) → "
              "s03b report (structural, relational, temporal, value, geographic, cross-source, lineage), including "
              "printed national totals and agreement between editions (stops on any FAIL).", INK),
             ("Provenance: every BBS value carries its yearbook edition and page; every source file and extract "
              "has a SHA-256 in manifest.csv, verified on each run.", MUTED)]
    y = 43
    for text, colour in notes:
        wrapped = textwrap.fill(text, 108)
        ax.text(0.0, y, wrapped, fontsize=FS, color=colour, va="top", linespacing=1.2)
        y -= LINE * 1.05 * (wrapped.count("\n") + 1) + 1.4
    fig.savefig(FIGURES / "fig8_lineage.png"); plt.close(fig)


if __name__ == "__main__":
    fig_pipeline(); fig_coverage(); fig_maps(); fig_coefficients(); fig_trends(); fig_flood_agreement()
    fig_lineage()
    print("figures written to", FIGURES)
