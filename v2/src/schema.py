"""Single specification of the v2 data model.

Used by the extraction step (expected variables per source-year), the
validation step (schemas, keys, coverage) and the data dictionary.
"""

# Source products: identifier, availability of the product itself, and the
# reason the period used in the panel starts or ends where it does.
PRODUCTS = {
    "bbs": dict(name="BBS Yearbook of Agricultural Statistics, 2012–2025 editions",
                provider="Bangladesh Bureau of Statistics", format="PDF tables",
                spatial="64 districts", available="each edition prints the two latest crop years",
                used="crop years 2010-11 to 2024-25 (harvest years 2011–2025)",
                licence="Public government statistics (PDFs not redistributed; obtain from bbs.gov.bd)"),
    "ndvi": dict(name="MODIS/061/MOD13Q1 (Terra NDVI, 16-day, 250 m)", provider="NASA LP DAAC via Google Earth Engine",
                 format="Raster (Earth Engine)", spatial="250 m, aggregated to district cropland",
                 available="February 2000 onward", used="January–April of harvest years 2011–2025",
                 licence="NASA open data"),
    "worldcover": dict(name="ESA/WorldCover/v200 (2021)", provider="European Space Agency via Google Earth Engine",
                       format="Raster", spatial="10 m", available="2020 and 2021 maps",
                       used="2021 map as a static cropland mask", licence="CC BY 4.0"),
    "climate": dict(name="ECMWF/ERA5_LAND/DAILY_AGGR", provider="Copernicus Climate Change Service via Google Earth Engine",
                    format="Raster", spatial="0.1°", available="1950 onward (about 3-month lag)",
                    used="November 2010 – May 2025", licence="Copernicus licence (free, with attribution)"),
    "jrc": dict(name="JRC/GSW1_4/MonthlyHistory (Landsat)", provider="European Commission JRC via Google Earth Engine",
                format="Raster", spatial="30 m", available="March 1984 – December 2021",
                used="monsoon Jun–Oct 2010–2021 (harvest years 2011–2022); flash Apr–May 2011–2021 "
                     "(harvest years 2011–2021); ends because the product ends in December 2021",
                licence="Copernicus programme, free with attribution"),
    "s1": dict(name="COPERNICUS/S1_GRD (IW, VV)", provider="European Space Agency via Google Earth Engine",
               format="Raster", spatial="10 m, analysed at 60 m",
               available="over Bangladesh from 3 October 2014",
               used="flash Apr–May 2015–2025 (harvest years 2015–2025); monsoon Jun–Oct 2015–2024 "
                    "(harvest years 2016–2025); the first complete Jun–Oct season is 2015",
               licence="Copernicus Sentinel data, free and open"),
    "srtm": dict(name="USGS/SRTMGL1_003", provider="NASA/USGS via Google Earth Engine", format="Raster",
                 spatial="30 m", available="static (2000)", used="slope mask for radar water detection",
                 licence="Public domain"),
    "gadm": dict(name="GADM v4.1, level 2", provider="GADM", format="Shapefile", spatial="64 district polygons",
                 available="static", used="district boundaries, areas and stable identifiers (GID_2)",
                 licence="Free for academic use; redistribution not permitted (users download from gadm.org)"),
}

# BBS yearbook edition -> PDF pages (1-based) of the district table
# "Estimates of Total Boro (Local+HYV+Hybrid)", located from the table titles.
BBS_PAGES = {
    2012: "90,91", 2013: "92,93", 2014: "90,91", 2015: "94,95",
    2016: "96,97", 2017: "95,96", 2018: "96,97", 2019: "96,97",
    2020: "92,93", 2021: "98,99", 2022: "98,99", 2023: "99,100",
    2024: "96,97", 2025: "97,98",
}

# Earth Engine extraction settings, read by s02_gee_extract.py and written to
# the metadata manifest.  A window (offset, m0, m1) covers months m0..m1 of
# year t + offset for harvest year t; if m0 > m1 it runs from m0 of that year
# to m1 of the next (e.g. (-1, 11, 5) = Nov t−1 – May t).
EXTRACTS = {
    "ndvi": dict(collection="MODIS/061/MOD13Q1", version="Collection 6.1 (061)",
                 bands="NDVI, SummaryQA", scale_m=250, windows={"season": (0, 1, 4)},
                 mask="ESA/WorldCover/v200 (2021) class 40 covering > 50 % of the MODIS cell; SummaryQA ≤ 1",
                 method="mean (ndvi_peak) and maximum (ndvi_max) of the 16-day composites in the window; "
                        "district mean over masked pixels"),
    "climate": dict(collection="ECMWF/ERA5_LAND/DAILY_AGGR", version="ERA5-Land daily aggregates",
                    bands="temperature_2m, temperature_2m_max, total_precipitation_sum", scale_m=1000,
                    windows={"season": (-1, 11, 5), "hot": (0, 3, 5)}, hot_threshold_c=35,
                    mask="none (land-only product)",
                    method="season mean of daily mean and daily maximum temperature; season total precipitation; "
                           "number of days with daily maximum > 35 °C in the hot window; district mean"),
    "jrc": dict(collection="JRC/GSW1_4/MonthlyHistory", version="v1.4", bands="water", scale_m=30,
                windows={"monsoon": (-1, 6, 10), "monsoon_dry": (-1, 1, 3),
                         "flash": (0, 4, 5), "flash_dry": (0, 1, 3)},
                mask="none",
                method="water (class 2) in any month of the window and not water in any month of the "
                       "matching dry window; share of district area; *_obs = share with ≥ 1 valid observation"),
    "s1": dict(collection="COPERNICUS/S1_GRD", version="GRD, IW mode, VV polarisation", bands="VV", scale_m=60,
               windows={"monsoon": (-1, 6, 10), "monsoon_dry": (-1, 1, 3),
                        "flash": (0, 4, 5), "flash_dry": (0, 1, 3)},
               threshold_db=-18, focal_median_m=50, slope_max_deg=5,
               mask="slope < 5° from USGS/SRTMGL1_003",
               method="monthly median VV, 50 m focal median, water if < −18 dB; water in any month of the "
                      "window and not water in the dry-window median; share of district area"),
}


def window(t, offset, m0, m1):
    """Start (inclusive) and end (exclusive) dates of a window for harvest year t."""
    y0 = t + offset
    y1 = y0 if m1 >= m0 else y0 + 1
    ey, em = (y1 + 1, 1) if m1 == 12 else (y1, m1 + 1)
    return f"{y0}-{m0:02d}-01", f"{ey}-{em:02d}-01"


# Variable -> (extract name, first harvest year, last harvest year) actually
# used.  A value is required for every district in every year of this range,
# and must be absent outside it.
COVERAGE = {
    "ndvi_peak": ("ndvi", 2011, 2025), "ndvi_max": ("ndvi", 2011, 2025),
    "tmean_c": ("climate", 2011, 2025), "tmax_c": ("climate", 2011, 2025),
    "precip_mm": ("climate", 2011, 2025), "hot_days": ("climate", 2011, 2025),
    "jrc_monsoon_flood": ("jrc", 2011, 2022), "jrc_monsoon_obs": ("jrc", 2011, 2022),
    "jrc_flash_flood": ("jrc", 2011, 2021), "jrc_flash_obs": ("jrc", 2011, 2021),
    "s1_monsoon_flood": ("s1", 2016, 2025), "s1_flash_flood": ("s1", 2015, 2025),
}

# Values that must be present in every row (the BBS panel has no gaps by
# construction; a missing value means an extraction or input error).
REQUIRED_NONNULL = {
    "bbs/bbs_boro_district_year.csv": ["district", "crop_year", "harvest_year", "area_ha", "yield_t_ha",
                                       "production_t", "book_year", "page"],
}

# Plausible ranges: values outside stop the pipeline for inspection; nothing
# is deleted or altered automatically.
RANGES = {
    "yield_t_ha": (1.0, 7.0), "area_ha": (0, 300000), "production_t": (0, 2_000_000),
    "ndvi_peak": (0.0, 1.0), "ndvi_max": (0.0, 1.0), "tmean_c": (10, 35), "tmax_c": (15, 40),
    "precip_mm": (0, 3000), "hot_days": (0, 92),
    "jrc_monsoon_flood": (0, 1), "jrc_flash_flood": (0, 1), "jrc_monsoon_obs": (0, 1),
    "jrc_flash_obs": (0, 1), "s1_monsoon_flood": (0, 1), "s1_flash_flood": (0, 1),
}

S, I, F = "VARCHAR", "BIGINT", "DOUBLE"
_D = ("district", S, "", "Canonical district name (64-district gazetteer)")
_Y = ("harvest_year", I, "year", "Boro harvest year t (crop grown Nov t−1 – May t)")

# Gold tables: grain, key, expected rows, columns (name, type, unit, description, source)
TABLES = {
    "dim_district": dict(
        grain="one row per district", key=["district_id"], rows=64, source="GADM v4.1 level 2",
        columns=[("district_id", S, "", "Stable identifier: GADM v4.1 GID_2"), _D,
                 ("division", S, "", "Administrative division (8)"),
                 ("area_km2", F, "km²", "District polygon area (UTM zone 46N), to 0.001 km²")]),
    "stg_bbs_boro": dict(
        grain="one row per district and harvest year", key=["district", "harvest_year"], rows=960,
        source="BBS yearbooks (Silver: silver_bbs_boro.parquet)",
        columns=[_D, _Y, ("crop_year", S, "", "BBS crop year as printed, e.g. 2012-13"),
                 ("area_ha", F, "ha", "Harvested Boro area"),
                 ("yield_t_ha", F, "t/ha", "Boro yield, husked rice per harvested hectare"),
                 ("production_t", F, "t", "Boro production, husked rice"),
                 ("bbs_edition", I, "year", "Yearbook edition the value was read from"),
                 ("bbs_page", I, "", "PDF page of the table in that edition")]),
    "stg_ndvi": dict(
        grain="one row per district and harvest year", key=["district", "harvest_year"], rows=960,
        source="MODIS MOD13Q1 v061 (Silver: silver_ndvi.parquet)",
        columns=[_D, _Y, ("ndvi_peak", F, "unitless", "Mean NDVI, Jan–Apr of t, cropland pixels, SummaryQA ≤ 1"),
                 ("ndvi_max", F, "unitless", "Maximum 16-day NDVI, Jan–Apr of t, cropland pixels")]),
    "stg_climate": dict(
        grain="one row per district and harvest year", key=["district", "harvest_year"], rows=960,
        source="ERA5-Land daily aggregates (Silver: silver_climate.parquet)",
        columns=[_D, _Y, ("tmean_c", F, "°C", "Mean 2 m temperature, Nov t−1 – May t"),
                 ("tmax_c", F, "°C", "Mean daily maximum 2 m temperature, Nov t−1 – May t"),
                 ("precip_mm", F, "mm", "Total precipitation, Nov t−1 – May t"),
                 ("hot_days", F, "days", "Days with daily maximum > 35 °C, Mar–May of t (district mean)")]),
    "stg_jrc": dict(
        grain="one row per district and harvest year", key=["district", "harvest_year"], rows=768,
        source="JRC GSW v1.4 monthly history (Silver: silver_jrc.parquet)",
        columns=[_D, _Y, ("jrc_monsoon_flood", F, "fraction", "Share of district area water in any month Jun–Oct t−1, not water Jan–Mar t−1"),
                 ("jrc_monsoon_obs", F, "fraction", "Share of district area with ≥ 1 valid JRC observation Jun–Oct t−1"),
                 ("jrc_flash_flood", F, "fraction", "Share of district area water in Apr or May t, not water Jan–Mar t"),
                 ("jrc_flash_obs", F, "fraction", "Share of district area with ≥ 1 valid JRC observation Apr–May t")]),
    "stg_s1": dict(
        grain="one row per district and harvest year", key=["district", "harvest_year"], rows=704,
        source="Sentinel-1 GRD IW VV (Silver: silver_s1.parquet)",
        columns=[_D, _Y, ("s1_monsoon_flood", F, "fraction", "Share of district area with monthly median VV < −18 dB in any month Jun–Oct t−1, not water Jan–Mar t−1; slope < 5°"),
                 ("s1_flash_flood", F, "fraction", "As above for Apr or May t against Jan–Mar t")]),
    "fact_boro_national": dict(
        grain="one row per harvest year", key=["harvest_year"], rows=15,
        source="stg_bbs_boro (district sums) and printed national rows",
        columns=[_Y, ("crop_year", S, "", "BBS crop year"),
                 ("area_ha", F, "ha", "Sum of district harvested area"),
                 ("production_t", F, "t", "Sum of district production"),
                 ("yield_t_ha", F, "t/ha", "production_t / area_ha"),
                 ("printed_national_production_t", F, "t", "National production printed in the table, where printed"),
                 ("printed_national_yield_t_ha", F, "t/ha", "National yield printed in the table, where printed")]),
    "fact_boro_panel": dict(
        grain="one row per district and harvest year", key=["district_id", "harvest_year"], rows=960,
        source="stg_bbs_boro joined to dim_district and the covariate staging tables",
        columns=[("district_id", S, "", "GADM v4.1 GID_2"), _D, ("division", S, "", "Administrative division"),
                 ("area_km2", F, "km²", "District area"), _Y, ("crop_year", S, "", "BBS crop year"),
                 ("yield_t_ha", F, "t/ha", "Boro yield (husked rice)"), ("area_ha", F, "ha", "Harvested Boro area"),
                 ("production_t", F, "t", "Boro production (husked rice)"),
                 ("bbs_edition", I, "year", "Source yearbook edition"), ("bbs_page", I, "", "Source PDF page"),
                 ("ndvi_peak", F, "unitless", "See stg_ndvi"), ("ndvi_max", F, "unitless", "See stg_ndvi"),
                 ("tmean_c", F, "°C", "See stg_climate"), ("tmax_c", F, "°C", "See stg_climate"),
                 ("precip_mm", F, "mm", "See stg_climate"), ("hot_days", F, "days", "See stg_climate"),
                 ("jrc_monsoon_flood", F, "fraction", "See stg_jrc"), ("jrc_flash_flood", F, "fraction", "See stg_jrc"),
                 ("jrc_monsoon_obs", F, "fraction", "See stg_jrc"), ("jrc_flash_obs", F, "fraction", "See stg_jrc"),
                 ("s1_monsoon_flood", F, "fraction", "See stg_s1"), ("s1_flash_flood", F, "fraction", "See stg_s1")]),
}

# Bronze files and the columns they must contain
BRONZE_FILES = {
    "bbs/bbs_boro_rows_all.csv": ["book_year", "page", "raw_name", "crop_year", "area_acres", "area_ha",
                                  "yield_maund_acre", "yield_t_ha", "production_t", "district", "row_type",
                                  "qc_ha", "qc_yield", "qc_prod", "qc_pass"],
    "bbs/bbs_boro_district_year.csv": ["district", "crop_year", "harvest_year", "area_ha", "yield_t_ha",
                                       "production_t", "book_year", "page"],
    "bbs/bbs_boro_national.csv": ["book_year", "crop_year", "area_ha", "yield_t_ha", "production_t"],
    "gee/ndvi_all.csv": ["district", "harvest_year"], "gee/climate_all.csv": ["district", "harvest_year"],
    "gee/jrc_all.csv": ["district", "harvest_year"], "gee/s1_all.csv": ["district", "harvest_year"],
}
