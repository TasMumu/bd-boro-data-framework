# 3. Study context and data sources

## 3.1 Bangladesh and the Boro crop

Bangladesh (147,570 km²) is divided into 64 districts in eight divisions. Boro rice is transplanted from December to February and harvested from late April to May, and is irrigated mainly from groundwater. Throughout this paper a Boro season is identified by its harvest year t: the crop grown from November of year t−1 to May of year t, which BBS reports as crop year "(t−1)–t". District boundaries are taken from GADM version 4.1 [@gadm2022]; no district boundary changed during the study period.

BBS publishes district estimates of Boro area, yield and production in its annual Yearbook of Agricultural Statistics. Each edition prints the two most recent crop years in a PDF table, so every crop year from 2011-12 to 2023-24 appears in two editions; 2010-11 appears only in the 2012 edition and 2024-25 only in the 2025 edition. The table layout, the page on which it appears and the spelling of district names change between editions, and the 2012 and 2013 editions group districts under former regions [@bbs2013; @bbs2026]. Floods affect Boro through two pathways: monsoon inundation in the months before planting, and pre-harvest flash floods, which in April 2017 destroyed rice worth an estimated US\$450 million in the north-eastern haor wetlands [@kamal2018]. Optical flood records such as the JRC Global Surface Water dataset [@pekel2016] are limited by monsoon cloud, whereas Sentinel-1 radar observes through cloud and has been used for flood mapping in Bangladesh [@uddin2019].

## 3.2 Sources, licences and access

Table 2 lists the sources. All can be obtained free of charge, but their access conditions and licences differ. No yield value is estimated, interpolated or modelled; a district-year enters the panel only if BBS printed it. Two inputs cannot be redistributed with the code: the BBS yearbook PDFs, which users download from the BBS website, and the GADM boundaries, whose licence does not permit redistribution. The satellite and climate data are extracted through Google Earth Engine [@gorelick2017], which requires a registered account; the district extracts used here are included in the repository, so an account is needed only to recompute them.

Table 2. Data sources, licences and access.

| Source | Variable(s) | Resolution | Licence and access |
|---|---|---|---|
| BBS Yearbook of Agricultural Statistics, 2012–2025 editions [@bbs2013; @bbs2026] | District Boro area, yield and production (husked rice) | 64 districts | Public statistics; PDFs from bbs.gov.bd, not redistributed |
| MODIS MOD13Q1 v061 [@didan2021] | NDVI, 16-day composites | 250 m | NASA open data; Earth Engine |
| ESA WorldCover v200 [@zanaga2022] | Cropland mask (2021 map) | 10 m | CC BY 4.0; Earth Engine |
| ERA5-Land daily aggregates [@munozsabater2021] | 2 m temperature, daily maximum, precipitation | 0.1° | Copernicus licence; Earth Engine |
| JRC Global Surface Water v1.4, monthly history [@pekel2016] | Monthly water presence | 30 m | Free with attribution; Earth Engine |
| Sentinel-1 GRD, IW, VV [@torres2012] | Backscatter for water detection | 10 m (analysed at 60 m) | Copernicus Sentinel data, free; Earth Engine |
| SRTM v3 [@farr2007] | Slope mask for radar water detection | 30 m | Public domain; Earth Engine |
| GADM v4.1 [@gadm2022] | District boundaries and identifiers | Vector | Academic use; from gadm.org, not redistributed |

## 3.3 Temporal coverage

The study period is set by the BBS statistics: the 14 editions from 2012 to 2025 cover crop years 2010-11 to 2024-25, that is, harvest years 2011–2025. Each covariate is extracted for every harvest year in that period for which its product provides the required months, and is left missing otherwise; series from different products are not spliced and no gap is filled (Table 3, Fig. 1). NDVI and climate cover all 15 seasons. The JRC monthly water history ends in December 2021, so it provides monsoon flood fractions (June–October of the preceding year) up to harvest year 2022 and flash flood fractions (April–May) up to 2021. Sentinel-1 data over Bangladesh begin in October 2014, so the first complete monsoon season is 2015 (harvest year 2016) and the first flash flood window is April–May 2015. Product availability and successful extraction are distinguished in Table 3: a district-year counts as extracted only if the value is present in the Gold panel. For the optical JRC record, cloud can leave parts of a district unobserved in a given month; the share of each district with at least one valid observation in the window is therefore stored with every JRC flood fraction.

Table 3. Product availability, extracted harvest years and observed district-years for each variable. For JRC, valid observations are the share of district area with at least one valid (cloud-free) observation in the window: the mean over district-years, with the minimum in parentheses.

{{ table_coverage }}

Fig. 1. Number of districts with observed data for each variable and Boro harvest year.

![](figures/fig2_coverage.png)
