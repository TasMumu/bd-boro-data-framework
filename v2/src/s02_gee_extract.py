"""Step 2 - District x harvest-year remote-sensing and climate variables from
Google Earth Engine.  Harvest year t = the Boro crop sown Nov(t-1), harvested
Apr-May(t) = BBS crop year "(t-1)-t".

Variables (all observed; no gap filling):
  NDVI      MODIS MOD13Q1 v061, 250 m, SummaryQA <= 1, cropland pixels only
            (ESA WorldCover v200 class 40 covering > 50 % of the MODIS cell).
            ndvi_peak = mean of Jan-Apr(t) composites (Boro vegetative to grain
            filling); ndvi_max = maximum Jan-Apr composite.
  Climate   ERA5-Land daily aggregates (0.1 deg), season Nov(t-1)-May(t):
            tmean_c, tmax_c (mean daily maximum), precip_mm (season total),
            hot_days (days with Tmax > 35 C in Mar-May(t), flowering window).
  Flood     Share of district area newly under water relative to the same
            year's dry season (Jan-Mar), so permanent rivers are excluded.
            monsoon_flood : water in any month Jun-Oct(t-1)   (antecedent)
            flash_flood   : water in Apr or May(t)            (pre-harvest)
            JRC GSW v1.4 MonthlyHistory (Landsat, 30 m)   1984-2021
            Sentinel-1 GRD VV, monthly median, < -18 dB    Oct 2014 onward
            The two sources are kept as separate variables (never spliced).

Collections, windows, thresholds and scales come from schema.EXTRACTS.
Results are cached per variable and year in v2/data/bronze/gee/.  Earth
Engine is contacted only when an extract is missing or incomplete, so the
pipeline runs from the cached extracts without an Earth Engine account.
"""
import json
import sys
import time
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd

from common import BRONZE, GEE_PROJECT, V2_BRONZE, canon_district
from schema import COVERAGE, EXTRACTS, window

OUT = V2_BRONZE / "gee"
OUT.mkdir(parents=True, exist_ok=True)
HARVEST_YEARS = range(2011, 2026)
TIMES = OUT / "extraction_times.json"     # seconds per variable-year, when computed
DATES = OUT / "extraction_dates.json"     # UTC date each extract was computed
ee = None                                 # Earth Engine module, loaded on first use


def setup_ee():
    """Initialise Earth Engine and the shared collections (first use only)."""
    global ee, FC, BD, MODIS, CROPLAND, ERA, JRC, S1, SLOPE_OK
    if ee is not None:
        return
    import ee as _ee
    ee = _ee
    ee.Initialize(project=GEE_PROJECT)
    g = gpd.read_file(BRONZE / "gadm_shapefiles" / "gadm41_BGD_2.shp")
    g["district"] = g.NAME_2.map(canon_district)
    g["geometry"] = g.geometry.simplify(0.001, preserve_topology=True)
    gj = json.loads(g[["district", "geometry"]].to_json())
    FC = ee.FeatureCollection([ee.Feature(ee.Geometry(f["geometry"]), {"district": f["properties"]["district"]})
                               for f in gj["features"]])
    BD = FC.geometry().bounds()
    MODIS = ee.ImageCollection(EXTRACTS["ndvi"]["collection"])
    CROPLAND = (ee.Image("ESA/WorldCover/v200/2021").eq(40).unmask(0)
                .reduceResolution(ee.Reducer.mean(), maxPixels=1024)
                .reproject(MODIS.first().projection()).gt(0.5))
    ERA = ee.ImageCollection(EXTRACTS["climate"]["collection"])
    JRC = ee.ImageCollection(EXTRACTS["jrc"]["collection"])
    S1 = (ee.ImageCollection(EXTRACTS["s1"]["collection"])
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filterBounds(BD).select("VV"))
    SLOPE_OK = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")).lt(EXTRACTS["s1"]["slope_max_deg"])


def reduce(img, scale, reducer=None, tile=8):
    reducer = reducer or ee.Reducer.mean()
    bands = img.bandNames().getInfo()
    if len(bands) == 1:
        # For a one-band image Earth Engine names the output after the
        # reducer ("mean"), not the band; name it explicitly.
        reducer = reducer.setOutputs(bands)
    res = img.reduceRegions(collection=FC, reducer=reducer, scale=scale, tileScale=tile)
    rows = res.select(["district"] + bands, retainGeometry=False).getInfo()
    return pd.DataFrame([f["properties"] for f in rows["features"]])


def expected_columns(name, year):
    """Variables each source can provide for harvest year t, given the
    product's actual availability (see schema.COVERAGE)."""
    return [v for v, (src, y0, y1) in COVERAGE.items() if src == name and y0 <= year <= y1]


def complete(df, name, year):
    """True if an extract has all 64 districts and a value for every
    variable that the source can provide for this harvest year."""
    need = expected_columns(name, year)
    return (len(df) == 64 and df.district.nunique() == 64
            and all(c in df and df[c].notna().all() for c in need))


def cached(name, year, fn):
    f = OUT / f"{name}_{year}.csv"
    if f.exists():
        df = pd.read_csv(f)
        if complete(df, name, year):
            return df
        print(f"  {name} {year}: cached extract incomplete, re-extracting", flush=True)
    setup_ee()
    for attempt in range(3):
        try:
            t0 = time.time()
            df = fn(year)
            df["harvest_year"] = year
            if not complete(df, name, year):
                raise ValueError(f"incomplete extract; expected {expected_columns(name, year)}, "
                                 f"got {list(df.columns)} with {len(df)} rows")
            df.to_csv(f, index=False)
            dt = time.time() - t0
            times = json.loads(TIMES.read_text()) if TIMES.exists() else {}
            times[f"{name}_{year}"] = round(dt, 1)
            TIMES.write_text(json.dumps(times, indent=1))
            dates = json.loads(DATES.read_text()) if DATES.exists() else {}
            dates[f"{name}_{year}"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            DATES.write_text(json.dumps(dict(sorted(dates.items())), indent=1))
            print(f"  {name} {year}: {len(df)} rows in {dt:.0f}s", flush=True)
            return df
        except Exception as e:                       # transient EE errors
            print(f"  {name} {year}: attempt {attempt + 1} failed: {e}", flush=True)
            time.sleep(10)
    raise RuntimeError(f"{name} {year} failed")


# ── NDVI ─────────────────────────────────────────────────────────────────
def ndvi(year):
    e = EXTRACTS["ndvi"]
    col = (MODIS.filterDate(*window(year, *e["windows"]["season"]))
           .map(lambda i: i.select("NDVI").multiply(0.0001)
                .updateMask(i.select("SummaryQA").lte(1))))
    img = ee.Image.cat(col.mean().rename("ndvi_peak"), col.max().rename("ndvi_max"))
    return reduce(img.updateMask(CROPLAND), e["scale_m"])


# ── Climate ──────────────────────────────────────────────────────────────
def climate(year):
    e = EXTRACTS["climate"]
    season = ERA.filterDate(*window(year, *e["windows"]["season"]))
    tmean = season.select("temperature_2m").mean().subtract(273.15).rename("tmean_c")
    tmax = season.select("temperature_2m_max").mean().subtract(273.15).rename("tmax_c")
    prec = season.select("total_precipitation_sum").sum().multiply(1000).rename("precip_mm")
    hot = (ERA.filterDate(*window(year, *e["windows"]["hot"])).select("temperature_2m_max")
           .map(lambda i: i.subtract(273.15).gt(e["hot_threshold_c"])).sum().rename("hot_days"))
    return reduce(ee.Image.cat(tmean, tmax, prec, hot), e["scale_m"])


# ── Flood: JRC monthly ───────────────────────────────────────────────────
def _jrc_water(year, w):
    """Water in any month of window w, and whether each pixel was observed."""
    offset, m0, m1 = w
    y = year + offset
    c = JRC.filter(ee.Filter.calendarRange(y, y, "year")).filter(ee.Filter.calendarRange(m0, m1, "month"))
    water = c.map(lambda i: i.eq(2)).max().unmask(0)
    seen = c.map(lambda i: i.gt(0)).max().unmask(0)
    return water, seen


def jrc_flood(year):
    e = EXTRACTS["jrc"]
    w = e["windows"]
    mon_w, mon_seen = _jrc_water(year, w["monsoon"])
    dry_prev, _ = _jrc_water(year, w["monsoon_dry"])
    bands = [mon_w.And(dry_prev.Not()).rename("jrc_monsoon_flood"),
             mon_seen.rename("jrc_monsoon_obs")]
    if "jrc_flash_flood" in expected_columns("jrc", year):      # JRC monthly ends Dec 2021
        fl_w, fl_seen = _jrc_water(year, w["flash"])
        dry_cur, _ = _jrc_water(year, w["flash_dry"])
        bands += [fl_w.And(dry_cur.Not()).rename("jrc_flash_flood"),
                  fl_seen.rename("jrc_flash_obs")]
    return reduce(ee.Image.cat(bands).clip(BD), e["scale_m"])


# ── Flood: Sentinel-1 ────────────────────────────────────────────────────
def _s1_water(start, end):
    e = EXTRACTS["s1"]
    c = S1.filterDate(start, end)
    vv = c.median().focal_median(e["focal_median_m"], "circle", "meters")
    return vv.lt(e["threshold_db"]).And(SLOPE_OK).unmask(0)


def _s1_monthly_any(year, w):
    offset, m0, m1 = w
    y = year + offset
    imgs = [_s1_water(*window(y, 0, m, m)) for m in range(m0, m1 + 1)]
    return ee.ImageCollection(imgs).max()


def s1_flood(year):
    e = EXTRACTS["s1"]
    w = e["windows"]
    need = expected_columns("s1", year)
    bands = []
    if "s1_monsoon_flood" in need:            # first complete Jun-Oct season is 2015
        mon = _s1_monthly_any(year, w["monsoon"])
        dry_prev = _s1_water(*window(year, *w["monsoon_dry"]))
        bands.append(mon.And(dry_prev.Not()).rename("s1_monsoon_flood"))
    fl = _s1_monthly_any(year, w["flash"])
    dry_cur = _s1_water(*window(year, *w["flash_dry"]))
    bands.append(fl.And(dry_cur.Not()).rename("s1_flash_flood"))
    return reduce(ee.Image.cat(bands).clip(BD), e["scale_m"])


def main(which):
    jobs = {
        "ndvi": (ndvi, HARVEST_YEARS),
        "climate": (climate, HARVEST_YEARS),
        "jrc": (jrc_flood, range(2011, 2023)),      # monsoon 2010-2021 / flash to 2021
        "s1": (s1_flood, range(2015, 2026)),        # flash 2015+, monsoon 2015+ (t>=2016)
    }
    for name in which:
        fn, years = jobs[name]
        print(f"[{name}]", flush=True)
        frames = [cached(name, y, fn) for y in years]
        pd.concat(frames).to_csv(OUT / f"{name}_all.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1:] or ["ndvi", "climate", "jrc", "s1"])
