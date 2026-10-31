---
title: "An open, tested data engineering framework for integrating official crop statistics with satellite and climate data: district-level Boro rice in Bangladesh"
---

::: {custom-style="Author"}
Tasnim Ahmad Mumu^a^, Rezaul Karim^b,\*^
:::

::: {custom-style="Affiliation"}
^a^ Department of Agronomy and Agricultural Extension, University of Rajshahi, Rajshahi 6205, Bangladesh

^b^ Department of Statistics and Data Science, University of Rajshahi, Rajshahi 6205, Bangladesh
:::

::: {custom-style="Correspondence"}
\* Corresponding author. E-mail address: mrkarim@ru.ac.bd (R. Karim); Tel.: +880 1726 433752
:::

# Abstract

Official crop statistics are often combined with satellite and climate data, but the integration is seldom tested. We present an open Python and DuckDB framework that extracts district Boro rice statistics from 14 Bangladesh Bureau of Statistics yearbooks, harmonises district names, and aligns the statistics by harvest year with cropland NDVI, ERA5-Land climate and two flood records. We evaluated it with matching metrics, a validation report, corrupted inputs and clean-environment rebuilds. All 5,182 source records, in 108 distinct spellings, matched 64 districts; for every crop year, district sums matched the published national total (from the yearbook text where tables print none); the validation report raised no failures; each of ten corrupted inputs stopped the pipeline with a diagnostic naming the failed check and the affected file, column or record; and in two fresh installations all 55 generated outputs matched the reference under stated rules. Code and derived data are open.

**Keywords:** data engineering; data validation; reproducibility; agricultural statistics; Sentinel-1; Bangladesh

# Software and data availability

- Name: bd-boro-data-framework
- Developer and contact: Tasnim Ahmad Mumu, University of Rajshahi; tasnimmumu414@gmail.com
- Year first available: 2026
- Hardware required: a standard desktop or laptop computer (tested on Windows-11 with 16 logical CPUs and 16 GB RAM)
- Software required: Python 3.11 or later (tested with 3.13.7) and the packages pinned in requirements-lock.txt (main packages in Appendix A); a Google Earth Engine account is needed only to re-extract satellite and climate data, since the extracts are included; pandoc is needed only to rebuild the manuscript
- Programming languages: Python and SQL (DuckDB)
- Documentation: README, a data dictionary generated from the specification, and two Jupyter notebooks (v2/notebooks) that build the dataset from the original sources step by step and document its evaluation
- Program size: 3,354 lines of code (176 KB), plus the test scripts
- Availability: https://github.com/TasMumu/bd-boro-data-framework (folder v2); the version described here is archived on Zenodo at https://doi.org/10.5281/zenodo.23795046
- Licence and cost: free of charge. The code is released under the MIT licence. The derived data in the repository remain subject to the terms of the sources they are derived from (Table 2); the MIT licence does not apply to them
- Data: the repository contains the derived data: the validated BBS district panel with the edition and page of every value, the Earth Engine district extracts, the district crosswalk, the validation report and the DuckDB analytical database. The BBS yearbook PDFs and the GADM boundaries are not redistributed and must be obtained from their publishers; the README explains how, and how to confirm from the SHA-256 checksums in the manifest that they are the files used.


# 1. Introduction

Agricultural monitoring increasingly combines government crop statistics with satellite observations and climate reanalysis. These sources arrive on different schedules, in different formats and at different spatial resolutions. Official statistics are often published only as tables in PDF reports, administrative units are spelled differently from one source to the next, and a crop season may span two calendar years. The steps that join such sources (table extraction, name matching, temporal alignment and quality control) can introduce errors that leave a dataset with the expected shape but the wrong values: a misread cell, a district matched to its neighbour, or a yield paired with the previous season's weather. Such errors propagate silently into every downstream model.

Computational reproducibility is widely advocated (Peng, 2011; Sandve et al., 2013; Wilson et al., 2017; Stodden et al., 2016) and is part of the FAIR principles for research data and software (Wilkinson et al., 2016; Barker et al., 2022), yet attempts to reproduce published results in hydrology and the geosciences often fail (Hutton et al., 2016; Konkol et al., 2019; Nüst et al., 2018). For data integration pipelines, sharing code and data is necessary but not sufficient. Users also need evidence that the quality checks would detect the errors they are meant to detect, and that the outputs can be rebuilt from the documented inputs in a new installation. Such evidence is rarely reported.

Bangladesh is a demanding test case. The irrigated dry-season Boro crop supplies a little over half of national rice production; BBS estimates Boro output at 21.3 million tonnes of husked rice in 2024-25 (Bangladesh Bureau of Statistics, 2026). District statistics are published each year in the Bangladesh Bureau of Statistics (BBS) Yearbook of Agricultural Statistics as PDF tables whose layout, district spellings and regional groupings change between editions (Bangladesh Bureau of Statistics, 2013–2025, 2026). Floods affect the crop through monsoon inundation before planting and through pre-harvest flash floods, and the two available satellite flood records cover different periods.

This paper presents an open data engineering framework that integrates BBS district Boro statistics with satellite, flood and climate data for all 64 districts of Bangladesh, and evaluates it against four questions:

- Q1. How completely, and how transparently, are district names harmonised across sources?
- Q2. Do the validation checks detect structural, relational, temporal, value, geographic, cross-source and lineage errors, and does the pipeline stop when an input is wrong?
- Q3. Are the outputs reproducible when the pipeline is rebuilt, including from a clean installation?
- Q4. What does it cost to run the pipeline, and what changes are needed to add a season or a source?

The contributions are:

- a Bronze–Silver–Gold pipeline in Python and DuckDB with a single schema specification, a district crosswalk with stable identifiers, explicit harvest-year alignment and value-level provenance;
- validation methods for official statistics published as PDF tables, which exploit the redundancy within the publications (units printed twice, national totals, years printed in two editions, regional groupings) in addition to generic schema, key and range checks;
- an evaluation of the framework with matching metrics, deliberately corrupted inputs, rebuilds in two clean environments with explicit comparison rules, and measured run times, all scripted so that they can be rerun;
- an open panel of 960 BBS district-years (64 districts, harvest years 2011–2025) in which every value is traceable to a yearbook edition and page, with satellite and climate covariates for their source periods.

Section 2 reviews related work, Section 3 describes the study context and data sources, Section 4 the framework design and Section 5 the evaluation methodology. Section 6 reports the results in the order of the evaluation, Section 7 discusses what the evaluation does and does not establish, and Section 8 concludes.


# 2. Related work

## 2.1 Integrating agricultural statistics with environmental data

Agricultural systems science depends on data infrastructures that link observations, models and decision tools (Janssen et al., 2017). Several recent datasets harmonise sub-national crop statistics: for the European Union with quality flags for each record (Ronchetti et al., 2024), and for 33 countries of sub-Saharan Africa (Lee et al., 2025). Global gridded yield products combine national statistics with satellite data (Iizumi and Sakai, 2020). Crop yield forecasting combines statistics with weather and remote-sensing predictors in modular workflows (Paudel et al., 2021) and in benchmark datasets that pair sub-national yields with weather, remote-sensing and soil predictors (Kallenberg et al., 2026); at field scale, multi-source pipelines automate the assembly of environmental predictors for yield models (Khidirova and Karakuş, 2026). On the satellite side, Earth-observation data cubes provide analysis-ready imagery (Lewis et al., 2017; Giuliani et al., 2017), openEO harmonises access to cloud processing back-ends (Schramm et al., 2021), and Google Earth Engine provides planetary-scale analysis of public archives (Gorelick et al., 2017).

In these systems official statistics generally enter as already tabulated inputs, and the work of digitising them, and of verifying the digitised values, is outside their scope. In Bangladesh, BBS district statistics have been used for national time-series and district trend analyses (Shahrier et al., 2025; Al Mamun et al., 2024), but without a published, checkable extraction. Table 1 summarises the datasets and frameworks closest to this study.

Table 1. Related datasets and frameworks compared with this study.

| Study | Scope | Crop statistics | Covariates | Focus |
|---|---|---|---|---|
| Ronchetti et al. (2024) | EU, 961 regions, 1975–2020 | National statistics and Eurostat, harmonised | None | Harmonised statistics with quality flags |
| Lee et al. (2025) | Sub-Saharan Africa, 33 countries | FEWS NET compilations, harmonised | None | Harmonised statistics |
| Iizumi and Sakai (2020) | Global, 0.5° grid, 1981–2016 | FAO statistics with satellite data | Used to model yields | Gridded yield estimates |
| Kallenberg et al. (2026) | Maize and wheat, multi-country | Published sub-national statistics | Weather, remote sensing, soil | Yield-forecasting benchmark |
| Khidirova and Karakuş (2026) | Field-scale rice | Field observations | Satellite, climate, soil, terrain | Feature pipeline for machine learning |
| Al Mamun et al. (2024) | Bangladesh, 64 districts, 2006–2020 | BBS (secondary data) | None | Trend analysis |
| This study | Bangladesh, 64 districts, 2011–2025 | BBS yearbook PDFs, validated value by value | Cropland NDVI, climate, monsoon and flash flood (two sensors) | Tested, reproducible integration pipeline |

The two closest frameworks show the difference in emphasis. UniCrop automates the acquisition, cleaning and harmonisation of satellite, meteorological, soil and terrain predictors for a given location, crop and period, and is evaluated by the accuracy of yield models trained on 557 field observations of rice (Khidirova and Karakuş, 2026): its target data are field observations, and its evaluation concerns prediction rather than the integration steps. CY-Bench pairs sub-national yield statistics, mostly from national statistics offices, with weather, remote-sensing and soil predictors aggregated to administrative units and aligned to the crop season; its yield data are filtered for zero or missing values and checked for consistency between yield, production and area, and their sources are documented in country-level data cards (Kallenberg et al., 2026). As far as we can determine from these publications, neither digitises statistics from PDF publications, checks the statistics against the publisher's printed totals or a second edition, records the provenance of each value, or reports tests in which known errors are introduced to show that its checks detect them. These are the elements this study adds.

## 2.2 Harmonising spatial units and names

Linking statistics across years and sources requires a stable set of spatial units. Boundary changes complicate longitudinal census data (Gregory and Ell, 2005) and have motivated longitudinal databases that re-express historical data in present-day units (Logan et al., 2014); global boundary datasets document the version and source of each unit (Runfola et al., 2020; GADM, 2022). Even where boundaries are stable, unit names differ between sources through transliteration, abbreviations and official spelling changes. Matching such names is a record-linkage problem (Christen, 2012). Fuzzy string matching resolves many variants automatically, but it can also assign a name to the wrong unit without warning, and the rules applied are seldom published with the dataset. The approach taken here is the opposite: an explicit list of observed variants, published with match statistics, and a pipeline that stops on any name it does not recognise.

## 2.3 Reproducible research software

Recommendations for reproducible computational research include scripting every step, recording software versions and sharing code and data (Peng, 2011; Sandve et al., 2013; Wilson et al., 2017; Stodden et al., 2016), and the FAIR principles have been extended from data to research software (Wilkinson et al., 2016; Barker et al., 2022). Practice lags behind: few computational hydrology studies can be reproduced from their publications (Hutton et al., 2016), and assessments of geoscientific and GIScience papers found that many could not be reproduced, most often because data, code or details of the computational environment were missing (Konkol et al., 2019; Nüst et al., 2018). A taxonomy of reproducible and replicable research has been proposed for environmental modelling (Essawy et al., 2020). Reproducibility claims are, however, usually supported by the availability of code and data rather than by a documented rebuild in a new environment with a stated criterion for what counts as the same result.

## 2.4 Data engineering architectures and data validation

Lakehouse platforms combine open file formats with warehouse-style management of analytical tables (Armbrust et al., 2021); the Bronze–Silver–Gold ("medallion") layering commonly used with them separates data as received from cleaned and integrated data, and embedded analytical databases such as DuckDB make the pattern practical on a single computer (Raasveldt and Mühleisen, 2019). Workflow managers such as Snakemake and targets rebuild only the steps whose inputs have changed and record the dependencies between them (Mölder et al., 2021; Landau, 2021). Data validation has been formalised as unit tests for data, declarative constraints checked on every batch (Schelter et al., 2018), and validating data is a central challenge in production machine-learning pipelines (Polyzotis et al., 2018). Data quality has several dimensions beyond accuracy, including completeness, consistency and interpretability (Wang and Strong, 1996), and provenance records how each value was derived (Simmhan et al., 2005). Open frameworks for environmental data handle climate data (Iturbide et al., 2019) and agricultural land-use data on Google Earth Engine (Zhang et al., 2020), both in this journal, and Earth-observation processing in agroecology (Graf et al., 2022).

Testing a system by deliberately introducing faults is established in software engineering and has been applied to the input data of machine-learning systems, one fault at a time (Rahal et al., 2023). Generic constraint checks (types, ranges, uniqueness, completeness) are necessary but cannot detect a misread or shifted cell whose value is still plausible. Official statistics, however, contain internal redundancy that can be checked: the same quantity in two units, district values that must sum to a printed total, and the same crop year printed in successive editions. We are not aware of an open framework that combines such value-level checks of digitised official statistics with explicit name harmonisation, crop-calendar alignment and satellite covariates, and that reports evidence that its checks detect deliberately introduced errors and that its outputs can be rebuilt in a clean environment.


# 3. Study context and data sources

## 3.1 Bangladesh and the Boro crop

Bangladesh (147,570 km²) is divided into 64 districts in eight divisions. Boro rice is transplanted from December to February and harvested from late April to May, and is irrigated mainly from groundwater. Throughout this paper a Boro season is identified by its harvest year t: the crop grown from November of year t−1 to May of year t, which BBS reports as crop year "(t−1)–t". District boundaries are taken from GADM version 4.1 (GADM, 2022); no district boundary changed during the study period.

BBS publishes district estimates of Boro area, yield and production in its annual Yearbook of Agricultural Statistics. Each edition prints the two most recent crop years in a PDF table, so every crop year from 2011-12 to 2023-24 appears in two editions; 2010-11 appears only in the 2012 edition and 2024-25 only in the 2025 edition. The table layout, the page on which it appears and the spelling of district names change between editions, and the 2012 and 2013 editions group districts under former regions (Bangladesh Bureau of Statistics, 2013–2025, 2026). Floods affect Boro through two pathways: monsoon inundation in the months before planting, and pre-harvest flash floods, which in April 2017 destroyed rice worth an estimated US\$450 million in the north-eastern haor wetlands (Kamal et al., 2018). Optical flood records such as the JRC Global Surface Water dataset (Pekel et al., 2016) are limited by monsoon cloud, whereas Sentinel-1 radar observes through cloud and has been used for flood mapping in Bangladesh (Uddin et al., 2019).

## 3.2 Sources, licences and access

Table 2 lists the sources. All can be obtained free of charge, but their access conditions and licences differ. No yield value is estimated, interpolated or modelled; a district-year enters the panel only if BBS printed it. Two inputs cannot be redistributed with the code: the BBS yearbook PDFs, which users download from the BBS website, and the GADM boundaries, whose licence does not permit redistribution. The satellite and climate data are extracted through Google Earth Engine (Gorelick et al., 2017), which requires a registered account; the district extracts used here are included in the repository, so an account is needed only to recompute them.

Table 2. Data sources, licences and access.

| Source | Variable(s) | Resolution | Licence and access |
|---|---|---|---|
| BBS Yearbook of Agricultural Statistics, 2012–2025 editions (Bangladesh Bureau of Statistics, 2013–2025, 2026) | District Boro area, yield and production (husked rice) | 64 districts | Public statistics; PDFs from bbs.gov.bd, not redistributed |
| MODIS MOD13Q1 v061 (Didan, 2021) | NDVI, 16-day composites | 250 m | NASA open data; Earth Engine |
| ESA WorldCover v200 (Zanaga et al., 2022) | Cropland mask (2021 map) | 10 m | CC BY 4.0; Earth Engine |
| ERA5-Land daily aggregates (Muñoz-Sabater et al., 2021; Copernicus Climate Change Service, 2019) | 2 m temperature, daily maximum, precipitation | 0.1° | Copernicus licence; Earth Engine |
| JRC Global Surface Water v1.4, monthly history (Pekel et al., 2016) | Monthly water presence | 30 m | Free with attribution; Earth Engine |
| Sentinel-1 GRD, IW, VV (Torres et al., 2012) | Backscatter for water detection | 10 m (analysed at 60 m) | Copernicus Sentinel data, free; Earth Engine |
| SRTM v3 (Farr et al., 2007) | Slope mask for radar water detection | 30 m | Public domain; Earth Engine |
| GADM v4.1 (GADM, 2022) | District boundaries and identifiers | Vector | Academic use; from gadm.org, not redistributed |

## 3.3 Temporal coverage

The study period is set by the BBS statistics: the 14 editions from 2012 to 2025 cover crop years 2010-11 to 2024-25, that is, harvest years 2011–2025. Each covariate is extracted for every harvest year in that period for which its product provides the required months, and is left missing otherwise; series from different products are not spliced and no gap is filled (Table 3, Fig. 1). NDVI and climate cover all 15 seasons. The JRC monthly water history ends in December 2021, so it provides monsoon flood fractions (June–October of the preceding year) up to harvest year 2022 and flash flood fractions (April–May) up to 2021. Sentinel-1 data over Bangladesh begin in October 2014, so the first complete monsoon season is 2015 (harvest year 2016) and the first flash flood window is April–May 2015. Product availability and successful extraction are distinguished in Table 3: a district-year counts as extracted only if the value is present in the Gold panel. For the optical JRC record, cloud can leave parts of a district unobserved in a given month; the share of each district with at least one valid observation in the window is therefore stored with every JRC flood fraction.

Table 3. Product availability, extracted harvest years and observed district-years for each variable. For JRC, valid observations are the share of district area with at least one valid (cloud-free) observation in the window: the mean over district-years, with the minimum in parentheses.

| Variable | Product availability | Harvest years | District-years with values | Valid observations, % of district area: mean (minimum) |
|--------------------------|--------------------------|------------|------------------|-----------------|
| Boro area, yield, production (BBS) | Each edition prints the two latest crop years | 2011–2025 | 960 of 960 | – |
| Peak-season NDVI (MODIS) | February 2000 onward | 2011–2025 | 960 of 960 | – |
| Temperature, precipitation, hot days (ERA5-Land) | 1950 onward (about 3-month lag) | 2011–2025 | 960 of 960 | – |
| Monsoon flood fraction, JRC | March 1984 – December 2021 | 2011–2022 | 768 of 768 | 98.8 % (72 %) |
| Flash flood fraction, JRC | March 1984 – December 2021 | 2011–2021 | 704 of 704 | 98.3 % (27 %) |
| Monsoon flood fraction, Sentinel-1 | Over Bangladesh from 3 October 2014 | 2016–2025 | 640 of 640 | – |
| Flash flood fraction, Sentinel-1 | Over Bangladesh from 3 October 2014 | 2015–2025 | 704 of 704 | – |

Fig. 1. Number of districts with observed data for each variable and Boro harvest year.

![](figures/fig2_coverage.png)


# 4. Framework design

## 4.1 Architecture

The pipeline follows the Bronze–Silver–Gold layering and stores analytical tables in DuckDB, an embedded analytical database (Raasveldt and Mühleisen, 2019) (Fig. 2). Bronze holds the sources as received, the yearbook PDFs and the Earth Engine district extracts, together with the rows parsed from the PDFs and a manifest of every file. Silver holds one validated Parquet table per source, keyed on district and harvest year. Gold holds the integrated panel, the source tables it is built from, a district dimension table and national totals, and is read by the analyses and the dashboard. Each step is a separate script; a single command (run_all.py) runs them in order, rebuilds every table, figure and the manuscript, and records the run time of each step. Earth Engine extracts are cached per variable and harvest year, so an interrupted run resumes and unchanged years are not recomputed.

Fig. 2. Data lineage as implemented: the files and tables written by each step, with the checks applied at each stage. Check identifiers in brackets stop the run when they fail.

![](figures/fig8_lineage.png){width=100%}

## 4.2 Data model and schema specification

One file (schema.py) specifies the data model: for every Gold table its grain, key, columns, types, units and sources; for every variable its plausible range and the harvest years in which it must be present; and for every source its product version, availability and licence. The data dictionary distributed with the code is generated from this file, and the same specification drives the extraction settings, the input checks and the validation report, so documentation and checks cannot drift apart. The Gold panel, fact_boro_panel, has one row per district and harvest year, keyed on a stable district identifier (district_id, the GADM GID_2 code) and the harvest year.

Inputs are checked against the specification before any table is built. Every Bronze file must contain its required columns; numeric columns must contain only numbers, so a text entry such as "n/a" is an error rather than a missing value; and the BBS area, yield and production must be present in every row. A violated rule raises an error whose message starts with a check identifier ([SCHEMA], [MISSING], [DISTRICT], [KEY] or [RANGE]) and names the file, column and records involved, and the run stops. Nothing is dropped or corrected silently.

## 4.3 District harmonisation and stable identifiers

All sources are mapped to one gazetteer of the 64 present-day districts. A source name is first compared with the canonical names after removing case, spaces and punctuation; names that still do not match are looked up in an explicit alias table that maps each observed variant to its canonical district (for example Jessore to Jashore and Comilla to Cumilla). The alias table holds only spellings that occur in at least one source, which the validation report checks, and no alias may repeat or collide with a canonical name. A name that matches neither the gazetteer nor the alias table stops the pipeline; it is never dropped or assigned by similarity. Every spelling found in the BBS yearbooks, GADM and the Earth Engine extracts is written to a published crosswalk with its source, the canonical district and identifier it maps to, the number of records and editions in which it occurs, and the rule used.

The 2012 and 2013 editions are organised by regions rather than districts: each region row is preceded by rows for the districts it contains. Five region rows (Bandarban, Khagrachhari, Rangamati, Mymensingh and Tangail) have no district rows beneath them. Because historical units can be larger than present-day districts (the former greater Mymensingh, for example, also covered present-day Jamalpur, Sherpur, Netrokona and Kishoreganj), these rows were assigned to a present-day district only after two tests. First, every other region row must equal the sum of the district rows listed under it, which shows that the regions partition into the listed districts and that the districts of the former greater units are reported under separate rows. Second, crop year 2012-13 is printed both in the region-structured 2013 edition and in the district-structured 2014 edition; each of the five region rows must equal the corresponding district row of the 2014 edition. A sum of k printed values was accepted as equal to a printed total if they differed by no more than 0.5 × (k + 1) units, the maximum discrepancy from rounding each value to a whole hectare or tonne.

## 4.4 Extraction and validation of BBS statistics

The district table "Estimates of Total Boro (Local + HYV + Hybrid)" was located in each of the 14 yearbook editions, its pages recorded in the specification, and read with camelot in lattice mode. Each district row reports harvested area in acres ($A_{ac}$) and hectares ($A_{ha}$), yield in maunds per acre ($Y_{md}$) and tonnes per hectare ($Y_{t}$), and production in tonnes ($P$). Using 1 acre = 0.404686 ha and 1 maund = 37.3242 kg, three relative discrepancies are computed:

$$E_A = \frac{|0.404686\,A_{ac} - A_{ha}|}{A_{ha}}, \qquad E_Y = \frac{|0.0373242\,Y_{md}/0.404686 - Y_{t}|}{Y_{t}}, \qquad E_P = \frac{|A_{ha}\,Y_{t} - P|}{P}.$$

A row is accepted only if $E_A$, $E_Y$ and $E_P$ are all at most 0.5 %, a tolerance that exceeds the error from rounding printed values but is far below the discrepancy produced by a misread or shifted cell. Rows with fewer than five numeric values per crop year are not parsed. The crop years of each row are read from the table header, and a row whose number of five-value blocks differs from the number of crop years in the header stops the extraction, as does a district printed twice in the same table: crop years are never assigned by position, and duplicate rows are never dropped. Failing rows are excluded and logged; no value is edited by hand. Next, the sum of district production in each edition and year is compared with the national total printed in the same table or, where the table has no national row, with the total quoted in the yearbook text. Finally, where a crop year is printed in two editions, the accepted row from the later edition is used and the two are compared; a district-year with no accepted row in any edition would be left missing.

## 4.5 Satellite and climate extraction and temporal alignment

Covariates are computed in Earth Engine and aligned to harvest year t (Table 4). Each is first computed for every pixel (a seasonal mean, total, count or maximum, or for flood a classification as seasonally inundated or not) and then averaged over the pixels in the GADM district polygon. NDVI and the climate variables are therefore district means of seasonal aggregates, and the flood variables are the proportion of district area classified as seasonally inundated. Before the reductions, the district polygons are simplified with a tolerance of 0.001° (about 0.1 km), preserving their topology, to keep the Earth Engine requests small. The date windows are defined once in the specification relative to t, so the same rule produces every year's extract and its documentation.

Table 4. Temporal alignment of variables to Boro harvest year t.

| Variable | Source | Window for harvest year t |
|--------------------------|--------------------------|--------------------------|
| Boro yield | BBS crop year (t−1)–t | Harvest Apr–May t |
| Peak-season NDVI | MODIS composites | Jan–Apr t |
| Mean temperature, mean daily maximum, season precipitation | ERA5-Land daily | Nov t−1 – May t |
| Hot days (Tmax > 35 °C) | ERA5-Land daily | Mar–May t |
| Monsoon flood fraction | JRC monthly / Sentinel-1 | Jun–Oct t−1, net of Jan–Mar t−1 water |
| Flash flood fraction | JRC monthly / Sentinel-1 | Apr–May t, net of Jan–Mar t water |

Peak-season NDVI is the mean of MOD13Q1 16-day composites from January to April of year t, covering the vegetative to grain-filling stages of Boro. Only pixels with the SummaryQA flag at 0 or 1 are used, and only cells in which cropland (WorldCover class 40) covers more than half of the 250 m cell. Mean temperature and mean daily maximum temperature are averaged over November t−1 to May t; season precipitation is the total over the same months. Hot days count the days from March to May of year t on which the daily maximum temperature exceeds 35 °C, the approximate threshold above which spikelet fertility in rice declines during flowering (Jagadish et al., 2007; Prasad et al., 2006).

The monsoon flood fraction is the share of district area observed as water in any month from June to October of year t−1 but not as water in January–March of year t−1. Subtracting dry-season water is intended to exclude permanent rivers and water bodies, so the variable measures the extent of seasonal inundation in the months before the Boro crop is planted. The flash flood fraction is the share of district area observed as water in April or May of year t but not in January–March of year t, measuring inundation during the harvest window. Both are computed separately from the JRC monthly water history (Landsat, 30 m) and from Sentinel-1. For Sentinel-1, monthly median VV backscatter was smoothed with a 50 m median filter and classified as water below −18 dB, a threshold in the range used for Bangladesh floodplains (Uddin et al., 2019; Twele et al., 2016), with slopes above 5° excluded. The dry-season baselines of the two sources differ: for JRC a pixel counts as dry-season water if it was water in any month from January to March, whereas for Sentinel-1 it counts if the median backscatter over January–March is below the threshold. Both variables describe inundation extent over the whole district, not flooding of Boro fields or crop damage.

Each extract is tested for completeness before it is used or cached: it must contain all 64 districts and a non-missing value of every variable that its product should provide for that harvest year. An incomplete extract is recomputed rather than reused, and an extract that is still incomplete after recomputation is not saved.

## 4.6 Provenance

Every BBS value in the Gold panel carries the yearbook edition and page from which it was read. A manifest written on every run lists each source file and extract with its SHA-256 checksum; for Earth Engine extracts it also records the product and version, the exact date windows used for that harvest year, the spatial scale, mask, method and parameters, the variables present, the number of rows, the date of extraction and the version of the Earth Engine client. The validation report recomputes every checksum, so a file that changes after the manifest was written is detected. Every computed result, table and figure in this paper is written by the pipeline to files from which the manuscript is generated, so no result is transcribed by hand, and a Streamlit dashboard reads the Gold tables and analysis outputs directly.


# 5. Evaluation methodology

The framework was evaluated against the four questions of Section 1. Table 5 links each question to the evidence collected and the output in which it is recorded. All evaluations are scripted and are rerun from the repository; none involves a manual step.

Table 5. Evaluation questions, evidence and outputs.

| Question | Evidence | Output |
|---|---|---|
| Q1 Name harmonisation | Matching metrics per source; crosswalk of every spelling | district_crosswalk.csv; table_district_matching.csv |
| Q2 Error detection | Validation report on every build; ten deliberately corrupted inputs at two stages; clean baseline run | validation_report.csv; failure_tests/results.csv and logs |
| Q3 Reproducibility | Repeated builds; rebuilds in two clean environments; file-by-file comparison | fresh_setup_summary.json; fresh_setup_comparison_*.csv |
| Q4 Run time and extension requirements | Measured run time of each step and of Earth Engine extraction per variable and year; the changes needed to add a season or a source (described; adding a source was not tested) | pipeline_timings.json; extraction_times.json |

## 5.1 District harmonisation (Q1)

A record is one row of a source table: a district row parsed from a yearbook table, a row of an Earth Engine extract (one per district, harvest year and product, holding all of that product's variables; the NDVI, climate, JRC and Sentinel-1 extracts are all included), or a GADM district polygon. For each source the matching table counts the records, the distinct spellings, and how each spelling was resolved: exactly, after normalising case, spacing and punctuation, through an alias rule, or as a verified single-district region row (Section 4.3). A spelling is counted once per source, however many records use it, and the extracts of the four Earth Engine products are counted together as one source. The number of unmatched spellings and of districts reached by each source are reported. Alias rules are reported in three ways: the number of rules in the gazetteer, the number used by the current data, and the number of spellings they resolve, counted once per source and once across all sources.

## 5.2 Validation report (Q2)

After every build, a validation step writes a report of checks in seven categories: structural (columns and types), relational (keys, row counts and joins), temporal (harvest-year rule and the declared coverage of each variable), value (completeness of the BBS values and declared ranges), geographic (name matching, boundaries and areas), cross-source (the BBS identities, totals, editions and region rows of Section 4) and lineage (edition and page of every BBS value, manifest checksums). Each check records the expected and observed result, the number of affected records and a status. A FAIL stops the run. INFO marks a condition that is expected and handled, and is reported rather than hidden. The number of checks is not itself a measure of quality: what matters is which kinds of error are covered and whether the checks fire when those errors occur, which the failure tests examine.

## 5.3 Deliberate failure tests (Q2)

Ten tests each damage a temporary copy of the data in one way that represents a common class of error, at two stages (Table 10). Six damage the Bronze inputs of the Silver and Gold build and exercise the generic checks: an unknown district name, a missing required column, a duplicated district-year, a value outside its valid range, text in a numeric column, and an empty BBS value. Four damage the rows parsed from the yearbook PDFs: two transposed digits in a production value, the printed lines of two districts exchanged, a row dropped from a crop year printed in only one edition, and a yield read from the wrong column. They exercise the checks applied to the parsed rows: the unit identities, the printed national totals and the comparison between editions, which use the redundancy of the yearbooks, and the completeness of the panel, which is the only check left where a crop year is printed once. For these, the BBS step is rerun from the damaged rows, so that the unit identities, the national-total check and the comparison between editions run exactly as they do on rows parsed from the PDFs. The real pipeline steps are then run on the damaged copy. A test passes only if the run stops at the expected step with a diagnostic that contains the expected check and names the affected file, column, table or record, and, where the damage breaks a unit identity, the row is also excluded and logged. A baseline run of the whole chain on an unmodified copy must complete, pass every validation check and reproduce the real BBS table and Gold panel exactly, as shown by identical SHA-256 checksums. The baseline is reported separately from the ten failure tests. The real data are never modified.

## 5.4 Reproducibility (Q3)

Reproducibility was assessed in two ways. First, the pipeline was rebuilt repeatedly on the same installation; all random procedures use fixed seeds, so every analysis output should be identical byte for byte. Second, a fresh-setup test followed the README from a clean state. It created a new folder containing only what a clone of the repository contains (code, tests, cached Earth Engine extracts, manuscript sources and two files that are kept in the repository rather than generated) and the external inputs the README asks users to download (the BBS yearbook PDFs and GADM boundaries). No generated file was present. Two new Python environments were created: environment A from requirements.txt, which pins only the direct dependencies, so that the installer chose current versions of all other packages; and environment B from a lock file that pins all packages to the versions that produced the results. In each environment the full pipeline, the failure tests and the manuscript build were run, and every generated file was compared with the reference outputs in the repository.

The comparison classes are defined in advance and are mutually exclusive (Table 6). A file is identical if its bytes match. Some formats store the time at which they were written or the folder in which they were run; these are compared by content instead. Files whose only differences are measured run times form a separate class, and two files that are kept in the repository rather than generated are checked for presence only. Any other difference, or any missing file, counts as a failure of the test. The test therefore distinguishes reproduction of the analysis outputs, which must be exact, from byte-level differences confined to file containers, folder paths and run times. The test was run on the same computer as the original analysis, in a separate folder and new environments, with copies of the downloaded inputs, and it did not repeat the Earth Engine extraction; these limits are discussed in Section 7.2.

Table 6. Classes used to compare the outputs of a fresh setup with the reference outputs, and the files that fell in each class in the final test (environment B).

| Class | Rule | Files in the final test |
|---------------------|--------------------------|--------------------------|
| Identical | SHA-256 of the two files equal | 42: data/bronze/bbs/ (7 csv files); data/bronze/manifest.csv; data/silver/ (5 parquet files); docs/data_dictionary.md; mappings/district_crosswalk.csv; outputs/failure_tests/ (5 csv/log files); outputs/figures/ (7 png files); outputs/results.json; outputs/validation_report.csv; outputs/validation_summary.json; outputs/tables/ (12 csv files) |
| Same content | DuckDB: every table equal value by value. Word: every document part equal, ignoring the write times stored in the file container. Logs: equal after removing the folder path | 10: data/gold/bangladesh_agri_v2.duckdb; outputs/failure_tests/ (7 log files); paper/reference.docx; paper_ems/Highlights.docx |
| Run time only | The only differences are measured run times (the run-time table and the sentence quoting the total run time) | 3: outputs/pipeline_timings.json; paper_ems/Manuscript_EMS.docx; paper_ems/Manuscript_EMS.md |
| Kept in repository | Not generated by the pipeline; checked for presence only | 2: outputs/failure_tests/s1_single_band_check.txt; outputs/figures/fig7_dashboard.png |
| Different | Any other difference, or a missing file; the test fails | 0 |

## 5.5 Run time and extension (Q4)

The wall-clock time of each pipeline step was recorded on a desktop computer (Windows-11, 16 logical CPUs, 16 GB RAM, Python 3.13.7). Earth Engine extraction time was recorded per variable and harvest year when each extract was first computed. Together these give the cost of rebuilding the pipeline and of adding a new season. The changes needed to add a new source are described from the design; adding one was not tested.

## 5.6 Consistency of the derived flood variables

Because the two flood sensors differ in sensitivity and cloud limitation, the JRC and Sentinel-1 series are kept as separate variables and are never spliced. Their agreement is measured on the district-years in which both exist: harvest years 2016–2022 for monsoon flooding and 2015–2021 for flash flooding, 64 districts in each year. District-years with only one sensor are excluded and nothing is imputed. Because the overlap consists of repeated observations of the same 64 districts, the pooled Pearson correlation is reported with a 95 % confidence interval from a cluster bootstrap that resamples whole districts (2,000 replicates), together with the correlation of the 64 district means (between-district agreement), the correlation of deviations from each district's mean (within-district, year-to-year agreement), and the mean bias, mean absolute error (MAE) and root mean square error (RMSE) of Sentinel-1 relative to JRC. Agreement between two sensors supports consistency but does not establish the accuracy of either. As an event-based consistency check, both series are also compared with the April 2017 flash flood in the north-eastern haor basin (Kamal et al., 2018), a well-documented event that should appear in the flood fractions and in the BBS statistics of the affected districts; the check shows whether the event is visible, but it does not measure the accuracy of either sensor.

## 5.7 Example application

To show that the Gold tables support a typical downstream analysis, a district vulnerability index was computed from them, with weight-sensitivity analysis and spatial cluster detection (Appendix B). This example illustrates use of the panel; it is not part of the evaluation of the framework.


# 6. Results

## 6.1 District harmonisation

The 5,182 district records in the three sources use 108 distinct spellings (Table 7). All were resolved to the gazetteer (0 unmatched), and every source reaches all 64 districts. In the BBS yearbooks, 60 of the 99 spellings match a canonical name exactly, 4 match after normalisation, 30 through alias rules (transliteration variants such as Sirajgonj and Hobigonj, and older English spellings such as Jessore and Comilla), and 5 are the verified single-district region rows of the 2012 and 2013 editions. GADM uses 10 names that differ from the canonical list, mostly older English spellings such as Bogra, Chittagong and Comilla. The gazetteer contains 34 alias rules, all of which are used by the current data. Counted once per source, they resolve 40 spellings (Table 7); counted once across all sources, 34 distinct spellings, because some spellings, such as Barisal, occur in more than one source. The total of 108 distinct spellings is likewise counted once across all sources. No name was matched by similarity.

Table 7. District name matching by source (distinct spellings counted once per source).

| Measure | BBS yearbooks | Earth Engine extract | GADM v4.1 |
|--------------------------|-------------|-----------|--------|
| Records | 1,726 | 3,392 | 64 |
| Distinct spellings | 99 | 65 | 64 |
| Exact | 60 | 64 | 54 |
| Normalised (case, spacing, punctuation) | 4 | 0 | 1 |
| Alias rule | 30 | 1 | 9 |
| Verified single-district region row | 5 | 0 | 0 |
| Unmatched | 0 | 0 | 0 |
| Districts reached | 64 | 64 | 64 |

## 6.2 Validation of the BBS statistics

The pipeline parsed 1,726 district rows from the 14 yearbook editions (28 edition–crop-year tables). All accepted rows satisfy the three identities with a maximum relative discrepancy of 0.15 %. Of the parsed rows, 4 failed, all in the 2012-13 columns of the 2013 edition and all on the yield identity alone ($E_Y$ between 2.4 % and 16.7 %, with area and production consistent), which indicates misprinted maund-per-acre values; the same district-years are printed consistently in the 2014 edition, which is used. In 24 of the 28 tables all 64 district rows were parsed; in the remaining four (the 2015 and 2018 editions, where part of the table did not parse) the same crop years are complete in another edition. Of the 24 complete tables, 18 print a national total, and the sum of district production equals it to within 0.001 %. The other six (both tables of the 2012, 2022 and 2023 editions) print no national row. They cover five crop years, three of which have a national total in another edition; for the remaining two the district sums agree with the totals quoted in the yearbook text: 18,616,780 t against "186.17 lac metric tons" for 2010-11 (2012 edition), and 20,185,943 t against "201,85,945 metric tons" for 2021-22 (2022 edition). The 2023 edition, from which the 2021-22 values in the panel are taken, prints the same district values as the 2022 edition. Crop years 2011-12 to 2023-24 are printed in two editions, giving 832 district-year pairs. For 766 of them a row was parsed in both editions; the other 66 lack a row in one edition because part of the 2015 and 2018 tables did not parse. Compared on area and yield, 6 of the 766 pairs differ, each by at most 1 ha of area, consistent with rounding (Table 8; Appendix Table C.1 traces every row from parsing to the panel).

Table 8. Extraction and validation of BBS district Boro estimates by crop year. The gap column gives the largest gap between the district sum and the printed national total over the complete tables that print one, with the edition(s) checked in parentheses, or the agreement with the total quoted in the yearbook text. Edition used gives the edition of the panel values, with the number of districts where two editions are used; where it differs from the edition checked, both editions print the same district values, apart from the six differences of at most 1 ha in 2013-14.

| Crop year | Harvest year | Editions | Districts | Rows failing checks | Gap to national total (edition checked) | Edition used |
|----------|-----------|-------------|-------------|-----------|--------------------------|-----------------------|
| 2010-11 | 2011 | 2012 | 64 | 0 | matches text total (2012) | 2012 |
| 2011-12 | 2012 | 2012, 2013 | 64 | 0 | < 0.001 % (2013) | 2013 |
| 2012-13 | 2013 | 2013, 2014 | 64 | 4 | < 0.001 % (2013, 2014) | 2014 |
| 2013-14 | 2014 | 2014, 2015 | 64 | 0 | < 0.001 % (2014) | 2015 (63), 2014 (1) |
| 2014-15 | 2015 | 2015, 2016 | 64 | 0 | < 0.001 % (2016) | 2016 |
| 2015-16 | 2016 | 2016, 2017 | 64 | 0 | < 0.001 % (2016, 2017) | 2017 |
| 2016-17 | 2017 | 2017, 2018 | 64 | 0 | < 0.001 % (2017) | 2018 (32), 2017 (32) |
| 2017-18 | 2018 | 2018, 2019 | 64 | 0 | < 0.001 % (2019) | 2019 |
| 2018-19 | 2019 | 2019, 2020 | 64 | 0 | < 0.001 % (2019, 2020) | 2020 |
| 2019-20 | 2020 | 2020, 2021 | 64 | 0 | < 0.001 % (2020, 2021) | 2021 |
| 2020-21 | 2021 | 2021, 2022 | 64 | 0 | < 0.001 % (2021) | 2022 |
| 2021-22 | 2022 | 2022, 2023 | 64 | 0 | matches text total (2022) | 2023 |
| 2022-23 | 2023 | 2023, 2024 | 64 | 0 | < 0.001 % (2024) | 2024 |
| 2023-24 | 2024 | 2024, 2025 | 64 | 0 | < 0.001 % (2024, 2025) | 2025 |
| 2024-25 | 2025 | 2025 | 64 | 0 | < 0.001 % (2025) | 2025 |

The region-structured editions reconcile with present-day districts. All 72 multi-district region rows in the 2012 and 2013 editions equal the sum of the district rows listed under them, to within rounding, and each of the five single-district region rows equals, to the hectare and the tonne, the district row printed for the same crop year in the 2014 edition (Appendix Table C.2). These rows are therefore estimates for the present-day districts and are used as such, after this reconciliation. The result is a complete BBS panel of 960 district-years, one for each of the 64 districts in each of the 15 seasons, with no missing value. Of these values, 10 come from single-district region rows (2010-11 and 2011-12), 33 from the earlier of two editions because the later table was incomplete, and the rest from district rows of the latest edition that prints them. These checks verify that each value was extracted correctly and assigned to the correct district and crop year; they do not verify the accuracy of the underlying survey estimates.

## 6.3 Validation report

The validation report of the final build contains 108 checks: 107 PASS, 1 INFO and 0 FAIL (Table 9). The INFO entry records the 4 BBS rows excluded by the unit identities (Section 6.2); they are logged with their discrepancies, and the same district-years enter the panel from the 2014 edition. Every source file and extract matched its manifest checksum, every BBS value carries its edition and page, every covariate is present for exactly its declared harvest years, and no join dropped or multiplied a record.

Table 9. Validation checks by category in the final build.

| Category | What is checked | Checks | PASS | INFO | FAIL |
|---------------|--------------------------|----------|--------|--------|--------|
| Structural | Required columns present in every Bronze file; Gold columns and types match the data dictionary | 15 | 15 | 0 | 0 |
| Relational | Keys unique and non-null; row counts; every district in dim_district; joins neither drop nor multiply records; non-missing values preserved through the joins | 39 | 39 | 0 | 0 |
| Temporal | Harvest-year rule; 15 consecutive seasons × 64 districts; each covariate present for exactly its declared years | 14 | 14 | 0 | 0 |
| Value | BBS values present in every row; every variable within its declared range | 16 | 16 | 0 | 0 |
| Geographic | Every source name maps to the gazetteer; alias rules used and non-colliding; GADM one-to-one; all 64 districts in each source; valid polygons, CRS and area sums | 13 | 13 | 0 | 0 |
| Cross-source | Unit identities; district sums against printed national totals and text totals; agreement between editions; region rows; national yield | 8 | 7 | 1 | 0 |
| Lineage | Edition and page recorded for every BBS value; SHA-256 of every source file and extract matches the manifest; every extract documented | 3 | 3 | 0 | 0 |

## 6.4 Deliberate failure tests

All ten failure tests passed (10 of 10; Table 10). The six tests on the Bronze inputs stopped the Silver and Gold build (s03) with a diagnostic giving the check identifier, the file and column and, where the error concerned specific records, the district and year. Three of the four tests on the parsed yearbook rows were caught by checks that use the redundancy of the yearbooks. The fourth, a row dropped from a crop year printed in only one edition, leaves an incomplete table, to which the national-total check does not apply, and no second edition to compare with; it was caught by the completeness check of the build. The transposed digits broke the identity between area, yield and production, so the row was excluded, and the district sum of the table no longer matched the printed national total, which stopped the validation step with a diagnostic naming the edition and crop year. The exchanged lines satisfied every identity and the national total, as expected, but disagreed with the 2020 and 2022 editions, which print the same crop years; the comparison between editions stopped the run and named the four district-years affected. The dropped row left a district-year without a BBS value, which stopped the build with a diagnostic naming Khulna 2025. The misread yield broke two identities, so the row was excluded, and it also disagreed with the other edition, by 38 t/ha, which the diagnostic reports as the largest yield difference. The baseline run completed, passed every validation check and reproduced the real BBS table and Gold panel with identical SHA-256 checksums (result: PASS).

Table 10. Deliberate failure tests at two stages: the first six damage the Bronze inputs of the Silver and Gold build, the last four the rows parsed from the yearbooks. Each test changes one input in a temporary copy; the real data are not modified.

| Test | Change to the input copy | Expected | Diagnostic | Result |
|--------------------|--------------------------|--------------------------|--------------------------|----------|
| Unknown district | BBS district 'Sunamganj' (2017) renamed to unknown 'Sunamgonjj' | stop at s03, [DISTRICT] | [DISTRICT] bbs: unrecognised district names ['Sunamgonjj'] in 1 record(s): Sunamgonjj 2017 | PASS |
| Missing column | required column ndvi_peak removed from gee/ndvi_all.csv | stop at s03, [SCHEMA] | [SCHEMA] gee/ndvi_all.csv: missing required columns ['ndvi_peak'] | PASS |
| Duplicate key | BBS record Sylhet 2020 duplicated | stop at s03, [KEY] | [KEY] bbs_boro: duplicate (district, harvest_year) keys [('Sylhet', 2020)] | PASS |
| Invalid value | NDVI for Rajshahi 2019 set to 1.7 (valid range 0–1) | stop at s03, [RANGE] | [RANGE] ndvi.ndvi_peak outside [0.0, 1.0] in 1 record(s): Rajshahi 2019 = 1.7 | PASS |
| Wrong type | BBS yield for Dhaka 2018 replaced by the text 'n/a' | stop at s03, [SCHEMA] | [SCHEMA] bbs/bbs_boro_district_year.csv: non-numeric values in numeric columns ['yield_t_ha']: yield_t_ha in 1 record(s): Dhaka 2018 = 'n/a' | PASS |
| Missing value | BBS yield for Bogura 2021 left empty | stop at s03, [MISSING] | [MISSING] bbs/bbs_boro_district_year.csv.yield_t_ha empty in 1 record(s): Bogura 2021 | PASS |
| Transposed digits | two digits of Rajshahi's 2019-20 production transposed in the 2021 edition (254,667 → 245,667 t) | stop at s03b, national-total check; row excluded by the unit identities | district sum = printed national total (complete tables): max 0.045828 % over 18 tables; 2021 edition, 2019-20: −0.046 % | PASS |
| Swapped rows | the printed lines of Dhaka and Bogura exchanged in the 2021 edition (both crop years) | stop at s03b, edition-agreement check | years printed in two editions agree: 4 of 10 differing pairs beyond rounding; largest differences 140,659 ha and 1.256 t/ha; Bogura 2019-20: 2020 edition 185,882 ha, 3.882 t/ha; 2021 edition 45,691 ha, 5.138 t/ha; … | PASS |
| Dropped row | Khulna's 2024-25 row removed from the 2025 edition, the only edition that prints that crop year | stop at s03, [MISSING] | [MISSING] fact_boro_panel: no BBS value for 1 district-year(s): Khulna 2025 | PASS |
| Misaligned cell | Bogura's 2019-20 yield in the 2021 edition read from the maund-per-acre column (3.882 → 42.08) | stop at s03b, edition-agreement check; row excluded by the unit identities | years printed in two editions agree: 1 of 7 differing pairs beyond rounding; largest differences 1 ha and 38.198 t/ha; Bogura 2019-20: 2020 edition 185,882 ha, 3.882 t/ha; 2021 edition 185,882 ha, 42.08 t/ha | PASS |

The tests also exposed defects during development, all corrected before the results reported here were produced. The wrong-type test at first ran to completion: the CSV reader converted the text "n/a" to a missing value, which the range checks then skipped. Numeric columns are now read strictly and the BBS values must be present ([MISSING]), and the missing-value test was added to cover this case. In the Earth Engine extraction, Sentinel-1 flash flood fractions were found to be missing for harvest year 2015, the only Sentinel-1 year processed as a single-band image, because Earth Engine names the output of a single-band reduction after the reducer rather than the band. Outputs are now named explicitly, and the completeness test of Section 4.5 rejects any extract that lacks an expected variable; recomputing harvest year 2016 through the single-band path reproduced the stored values to within 10⁻¹⁶. Finally, the first fresh-setup test found two sources of spurious differences: the manifest recorded file modification times, which change when files are copied, and district areas differed in the fifteenth significant digit between versions of the geometry libraries. Extraction dates are now recorded when each extract is computed, and areas are rounded to 0.001 km². A later fresh-setup run showed that the manuscript build failed in a clean copy when no failure-test results existed yet; it now marks the manuscript as a draft instead.

## 6.5 Reproducibility

Repeated builds on the same installation produced byte-identical analysis outputs and the same Gold panel checksum. The fresh-setup test passed in both environments (Table 11). In environment A the installer chose versions different from the lock file for 64 of 103 packages, among them the geometry libraries shapely and pyproj; in environment B every package matched the lock file. In both environments the pipeline completed, the validation report raised no failures, the ten failure tests and the baseline passed, and each of the 57 files fell into one class of Table 6. Of the 55 generated outputs, 42 were byte-identical, 10 had the same content in a file that stores write times or folder paths (the Gold database, the failure-test logs and two Word files), and 3 differed only in measured run times (the timing record and the manuscript in its Markdown and Word versions); the other 2 files are kept in the repository rather than generated. No file differed in any other way. Every analysis output, including the Silver and Gold data, the analysis tables and results and the generated figures, was therefore reproduced exactly, and byte-level differences were confined to file containers, folder paths and run times. Earth Engine was not contacted in either environment, because every cached extract passed the completeness test. The dataset was also rebuilt from the original sources in the notebook distributed with the code (01_Data_Engineering_Pipeline.ipynb), which carries out the same steps cell by cell alongside their documentation: all 25 Bronze, Silver and Gold files and tables it built were identical to those of the command-line pipeline, as was the checksum of the Gold panel. In the same notebook, the NDVI extract for harvest year 2016 was recomputed from Earth Engine for all 64 districts and differed from the stored extract by at most 3 × 10⁻¹⁶.

Table 11. Fresh-setup test in two clean environments. Package counts include all installed packages; the last five rows classify the 57 output files under the rules of Table 6.

| Measure | Environment A (requirements.txt) | Environment B (requirements-lock.txt) |
|--------------------------|----------------------|--------------------------|
| Packages installed | 103 | 103 |
| Packages differing from the lock file | 64 | 0 |
| Pipeline (run_all.py) | completed, 202 s | completed, 173 s |
| Validation report | 107 PASS, 1 INFO | 107 PASS, 1 INFO |
| Failure tests passed | 10 of 10 | 10 of 10 |
| Baseline run | passed | passed |
| Gold panel checksum | equal | equal |
| Files compared | 57 | 57 |
| Identical | 42 | 42 |
| Same content | 10 | 10 |
| Run time only | 3 | 3 |
| Kept in the repository | 2 | 2 |
| Different | 0 | 0 |

## 6.6 Run time and extension

Table 12 lists run times on the reference computer. Rebuilding the whole pipeline from the yearbook PDFs and the cached Earth Engine extracts takes about 3 minutes, dominated by PDF table extraction and the spatial robustness analysis of the example application; in the fresh environments, which include the manuscript build, a full run took 202 s and 173 s. Extracting one harvest year from Earth Engine takes between 21 and 201 seconds depending on the product, about 6 minutes for all four. Adding a season therefore requires the page numbers of the new yearbook table in the specification, a few minutes of Earth Engine extraction and a rebuild, after which the validation report checks the new season like any other. Adding a new source requires a specification of its table, an extraction step that writes a Bronze file keyed on district and harvest year, and a join in the Gold build; this path was not exercised in the evaluation. The Gold warehouse occupies 4.0 MB.

Table 12. Run times of the pipeline steps (Windows-11, 16 logical CPUs, 16 GB RAM).

| Step | Run time |
|--------------------------|--------|
| BBS extraction and validation | 65 s |
| Earth Engine extraction (cached) | 3 s |
| Metadata manifest | 2 s |
| Silver and Gold layers | 3 s |
| Validation report | 3 s |
| Statistical analysis | 67 s |
| Figures | 7 s |
| Manuscript template | 0 s |
| ERA5-Land climate (per harvest year, uncached) | 21 s |
| JRC flood (per harvest year, uncached) | 201 s |
| NDVI (per harvest year, uncached) | 35 s |
| Sentinel-1 flood (per harvest year, uncached) | 111 s |

## 6.7 Consistency of the derived flood variables

The two flood sources agree strongly over their overlap period (Table 13, Fig. 3). For monsoon flooding (harvest years 2016–2022, 448 district-years), the pooled correlation between JRC and Sentinel-1 district fractions is 0.94 (95 % cluster-bootstrap interval 0.86–0.96), and the mean bias is 0.4 percentage points of district area. The agreement is driven mainly by differences between districts (correlation of district means 0.96); agreement on year-to-year variation within districts is moderate (0.59). For flash flooding (harvest years 2015–2021, 448 district-years), the pooled correlation is lower (0.84, interval 0.64–0.88) and less certain, as expected for a short April–May window in which a single cloud-free Landsat scene can decide whether flooding is observed, but the within-district agreement is higher (0.77), reflecting large, shared year-to-year signals such as the 2017 flood.

Table 13. Agreement between Sentinel-1 and JRC flood fractions over the overlap period (N = district-years, with districts in parentheses). Pooled r uses all district-years, with a 95 % interval from a cluster bootstrap over districts; district-mean r correlates the district means; within-district r correlates deviations from district means. Bias, MAE and RMSE are Sentinel-1 minus JRC, in percentage points (pp) of district area.

| Statistic | Monsoon flood fraction | Flash flood fraction |
|--------------------------|-------------------|-------------------|
| Harvest years | 2016–2022 | 2015–2021 |
| District-years (districts) | 448 (64) | 448 (64) |
| Pooled r (95 % CI) | 0.94 (0.86–0.96) | 0.84 (0.64–0.88) |
| District-mean r | 0.96 | 0.93 |
| Within-district r | 0.59 | 0.77 |
| Bias (pp) | +0.42 | −0.17 |
| MAE (pp) | 2.43 | 1.09 |
| RMSE (pp) | 3.62 | 2.68 |

Fig. 3. Agreement between JRC (Landsat) and Sentinel-1 flood fractions for the same districts and harvest years. Dashed line: 1:1.

![](figures/fig6_flood_agreement.png)

The April 2017 flash flood provides an event-based consistency check (Table 14). The six districts with the largest Sentinel-1 flash flood fractions in 2017 all lie in the north-eastern haor basin where the event occurred (Kamal et al., 2018), and JRC ranks the same six districts highest, in a slightly different order. In these districts BBS harvested area fell by 15–72 % and production by 16–72 % relative to 2015–2016, while reported yield changed by no more than 3.8 %. The changes in the official statistics are consistent with the documented event, and in the most affected districts they appear in harvested area and production rather than in yield. The comparison is observational: it does not attribute the whole decline to flooding or measure flood losses.

Table 14. The April 2017 flash flood: Sentinel-1 and JRC flash flood fractions and the change in BBS harvested area, yield and production relative to the 2015–2016 mean (the eight districts with the largest Sentinel-1 fractions; the first six lie in the north-eastern haor basin).

| District | Flash flood, Sentinel-1 (%) | Flash flood, JRC (%) | Harvested area (%) | Yield (%) | Production (%) |
|---------------|--------------|----------|-------------|---------|--------------|
| Sunamganj | 44.7 | 37.2 | −71.5 | −0.1 | −71.5 |
| Kishoreganj | 27.0 | 30.0 | −31.4 | +3.8 | −28.7 |
| Netrokona | 17.4 | 16.2 | −21.2 | +0.3 | −21.0 |
| Sylhet | 12.7 | 26.7 | −18.8 | −0.3 | −19.1 |
| Habiganj | 10.2 | 14.1 | −14.8 | −1.6 | −16.2 |
| Moulvibazar | 8.4 | 9.5 | −21.3 | −0.2 | −21.5 |
| Lalmonirhat | 7.9 | 0.4 | −2.8 | +3.2 | +0.2 |
| Brahmanbaria | 5.8 | 5.7 | −4.9 | +1.2 | −3.8 |

## 6.8 The integrated panel and an example application

The Gold panel holds 960 district-years with BBS area, yield and production, and each covariate for its source period (Table 3; descriptive statistics in Appendix Table D.1). District Boro yield averaged 4.014 t/ha of husked rice (SD 0.448), and national yield, computed from the district totals, rose from 3.903 t/ha in 2011 to 4.361 t/ha in 2025, matching the national yields printed by BBS to within 0.0005 t/ha.

The example vulnerability index computed from the Gold tables (Appendix B) ranks highest the north-eastern districts in and near the haor basin, the coastal districts Patuakhali and Barguna, and the western districts Chapai Nawabganj and Meherpur. Its rankings are reasonably stable under 10,000 random weightings of its five components (median Spearman correlation with the equal-weight ranking 0.80), and global Moran's I is significant under 100 % of 1,000 weightings, with a north-eastern high–high cluster as the most frequent but not the only pattern (Fig. 4). The Streamlit dashboard (Fig. 5) provides a national overview, a district explorer for every panel variable, the index and cluster maps, and a data-quality page with the BBS extraction checks of Table 8. Because it reads the Gold tables and analysis outputs directly, its figures cannot diverge from those in this paper.

Fig. 4. Example application. (a) Vulnerability index; numbers mark the five highest-ranked districts (1 Sunamganj, 2 Patuakhali, 3 Kishoreganj, 4 Barguna, 5 Sylhet). (b) LISA clusters at pseudo p < 0.05 (9,999 permutations, fuzzy contiguity weights); outlined districts remain significant after FDR correction.

![](figures/fig3_vulnerability_lisa.png)

Fig. 5. Overview page of the dashboard.

![](figures/fig7_dashboard.png)


# 7. Discussion and limitations

## 7.1 What the framework contributes

Integrating official statistics published as PDF tables carries risks that range checks and summary statistics do not reveal, because the resulting dataset still has the expected shape. Three are specific to sources like the BBS yearbooks. First, crop years span two calendar years; keying the Boro season "(t−1)–t" to the sowing year rather than the harvest year would pair every yield with satellite and climate data from the previous season. The framework therefore declares the crop calendar explicitly and keys every table on harvest year. Second, table structures change between editions: the 2012 and 2013 editions group districts under former regions, and a parser that recognises only district rows would silently drop five districts from two complete seasons. Third, table extraction can fail on part of a page, as it did for two editions here; the resulting gaps are tempting to fill by interpolation or modelling, which would mix estimated and observed values.

The framework addresses these risks with checks that use the redundancy of the publications themselves. Reconciling every extracted table with the publisher's own national totals detects missing or misread rows; comparing the two editions in which each year appears detects parsing and revision errors; and recording the edition and page of every value makes any remaining question answerable by opening the yearbook. Gaps are filled from another edition of the same table, never by estimation. Name harmonisation is equally explicit: every spelling is listed in the crosswalk with the rule that resolved it, the alias table holds only variants that occur in the data, and an unrecognised name stops the run instead of being matched by similarity. These checks are cheap to implement, and we suggest they should be standard whenever official statistics are digitised from PDF.

The evaluation adds evidence that is rarely reported for data integration pipelines: that the checks fire on the errors they are designed to catch, with diagnostics that point to the record, and that the outputs can be rebuilt from the documented inputs in new environments under stated comparison rules. The failure tests were also useful during development, where they exposed a check that could be bypassed (text in a numeric column); a variable missing from one year of the satellite extraction, found during development, is now caught by the completeness test. Both evaluations are scripts in the repository, so they can be rerun whenever the code or the data change.

## 7.2 What the evaluation does not establish

The checks verify that each value was extracted correctly and assigned to the correct district and season; they do not verify the BBS survey estimates themselves, which are subject to sampling and revision error and have not been compared here with independent area estimates. A value can also pass every check and still be wrong, if the error is in the publisher's own tables, is repeated across editions and is included in the printed totals. Chandpur in 2016–17 appears to be such a case: its 110,467 ha is far above the 62,341 ha before and 67,733 ha after, and the yearbooks print the same area for HYV and hybrid Boro that year, about ten times its hybrid area in the adjacent years. We keep the value as printed, because values are never edited by hand, and flag it for users. The ten failure tests represent common classes of error, not every possible error. The exchanged-lines test shows that a row attributed to the wrong district passes the unit identities and the national total and is caught only by the comparison between editions; in the two crop years printed in a single edition (2010-11 and 2024-25), such an error would not be detected. The validation ranges are wide plausibility bounds and would not detect a plausible but wrong covariate value.

The fresh-setup test supports reproducibility from the documented local inputs, not full independent reproduction from the original public sources. It ran on the same computer and operating system as the original analysis, in a separate folder and new environments; Linux and macOS were not tested. The BBS yearbooks and GADM boundaries were copies of the files used, so their checksums matched by construction, and downloading them again was not tested; the manifest allows a user to confirm that their downloads are identical. The Earth Engine extraction was not repeated in full: the extracts are taken from the repository, and recomputation was checked for two extracts of harvest year 2016, Sentinel-1 through the single-band path and NDVI. Earth Engine collections can be reprocessed by their providers, so a future re-extraction may differ slightly; the manifest records the product version, parameters and extraction date of every extract for that reason. Finally, the comparison classes accept differences in run times, write times and folder paths; they are stated in Table 6 so that the criterion is explicit, and every analysis output had to match exactly. Run times also varied between runs on the same computer, so the reported times indicate the order of magnitude rather than a benchmark.

## 7.3 Source coverage

No single flood record covers the whole study period. The JRC monthly water history ends in December 2021, and Sentinel-1 begins in October 2014, so the two series overlap only in harvest years 2016–2022 for monsoon flooding and 2015–2021 for flash flooding, and they are not spliced. Analyses that need a flood variable for all of 2011–2025 must therefore either use the two series separately or justify a combination, for which the agreement statistics of Table 13 are a starting point. For monsoon flooding the two sensors agree closely on which districts flood most, but only moderately on year-to-year variation within a district, so they are interchangeable for describing spatial exposure but not for analyses that rely on annual anomalies. Flash flood fractions agree less overall, as expected for a short and often cloudy window in which optical sensors can miss short-lived inundation that radar observes (Uddin et al., 2019; Twele et al., 2016), but both capture large events such as the 2017 flood.

The 2017 comparison is also consistent with BBS recording crop destroyed before harvest as lost harvested area rather than as lower yield. BBS estimates yield from crop cuts on sample plots in fields growing the crop, estimates area separately from sample clusters, and derives production by multiplying the two (Bangladesh Bureau of Statistics, 2026). Its crop report for 2016–17 states that flash flood fully damaged Boro on 296,701 ha, and national Boro area fell by about that amount that year (Bangladesh Bureau of Statistics, 2013–2025). In Sunamganj, BBS harvested area and production both fell by 72 % in 2017, while yield was almost unchanged (Table 14). Analyses that relate weather or flood exposure to BBS district yield alone can therefore understate damage from events that destroy whole fields, which is why the panel provides harvested area and production alongside yield.

## 7.4 Portability and maintenance

The components of the framework are general: a gazetteer that maps every source spelling to one list of units, table extraction with arithmetic and total checks, a declared crop-calendar alignment, Earth Engine extraction cached per variable and year, a single specification of tables and checks, and scripted failure and reproducibility tests. They carry over to other countries that publish sub-national crop statistics as PDF tables, and to other crops reported in the BBS yearbooks (Aus and Aman rice, wheat, potato and jute) by changing the table locations and the calendar windows. Table locations were identified once per edition and are recorded in the specification, so a new edition needs at least its page numbers in the specification, and a layout that the table extractor cannot read would also need changes to the parsing code; and a new spelling stops the pipeline until it is added to the alias table. The framework depends on Google Earth Engine for satellite and climate extraction and on the GADM licence for boundaries; the cached extracts and the manifest reduce, but do not remove, these dependencies.

## 7.5 Limitations of the derived variables

Both flood variables measure inundation extent, not crop damage. They are computed over the whole district, so detected water may lie on land not cultivated with Boro; the dry-season baseline may not remove all permanent water, because water detection varies between months; and the monsoon fraction describes conditions before the crop is planted. The dry-season baseline (January–March) also coincides with Boro transplanting, when fields stand in water. If these paddies are classified as water, inundation of the same land is removed from the flood fractions: from the monsoon fraction for fields planted in January–March of year t−1, and from the flash flood fraction for the current crop. The flood fractions may therefore underestimate inundation of Boro land. Much monsoon inundation is normal on the floodplain, so separating damaging floods from normal inundation would require comparison with a longer flood climatology. The Sentinel-1 water threshold (−18 dB) and the 50 % cropland rule are fixed choices; apart from the 2017 event and the agreement between sensors, the flood fractions have not been validated against field observations. The cropland mask is static (2021) and not specific to Boro, so NDVI also reflects other dry-season crops. The example vulnerability index covers exposure and production sensitivity only, omitting salinity (Sarkar et al., 2023), groundwater depletion (Shamsudduha et al., 2012), irrigation access and socio-economic capacity, and the location of its high–high cluster depends on the weights; it should guide where to look more closely rather than serve as an allocation rule (Tate, 2012; Saisana et al., 2005).


# 8. Conclusions

This paper presented and evaluated an open Bronze–Silver–Gold data engineering framework, implemented in Python and DuckDB, that integrates official BBS district Boro statistics with satellite, flood and climate data for all 64 districts of Bangladesh. Every one of the 960 district-year values is read from a printed BBS table, checked against unit identities, reconciled with the national total and with a second edition where one exists, assigned to a present-day district and aligned to the Boro harvest year; no value is imputed. The evaluation showed that all 5,182 district records across the sources were matched to the 64 districts through published rules, that the validation report raised no failures, that each of ten deliberately corrupted inputs stopped the pipeline with a diagnostic naming the problem, and that in two clean environments every generated output matched the reference under explicit comparison rules, with byte-level differences confined to file containers, folder paths and run times. The evidence has stated limits: it concerns the extraction and integration, not the accuracy of the survey estimates or of the satellite variables, and the fresh-setup test used local copies of the inputs on one computer. What can be reused is the combination of value-level checks of digitised statistics, explicit name harmonisation, declared temporal alignment, provenance for every value, and scripted tests that show the checks work. The code and the derived data, including the crosswalk, the validation report and the analytical warehouse, are openly available, the BBS yearbooks and GADM boundaries can be obtained from their publishers, and the pipeline and its tests can be rerun with single commands.

# CRediT authorship contribution statement

Tasnim Ahmad Mumu: Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Writing – original draft, Writing – review & editing, Visualization. Rezaul Karim: Supervision, Methodology, Validation, Writing – review & editing.

# Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

# Declaration of competing interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

# Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the authors used Claude (Anthropic) to assist with code development, data validation and analysis scripts, and drafting and editing of the manuscript text. After using this tool, the authors reviewed and edited the content as needed and take full responsibility for the content of the published article.

# Data availability

The code (MIT licence) and the derived data are available in the repository given in the Software and data availability section and archived at https://doi.org/10.5281/zenodo.23795046; the derived data remain subject to the terms of their sources (Table 2). Contains modified Copernicus Sentinel data (2014–2025) and modified Copernicus Climate Change Service information (2026). The BBS yearbook PDFs and the GADM v4.1 boundaries are not redistributed and must be obtained from the Bangladesh Bureau of Statistics and gadm.org; the manifest in the repository lists the SHA-256 checksum of each file used.


# References

Al Mamun, M.A., Nihad, S.A.I., Sarker, M.R., Sarkar, M.A.R., Hossain, M.I., Kabir, M.S., 2024. Spatiotemporal mapping of rice acreage and productivity growth in Bangladesh. PLOS ONE 19 (3), e0300648. https://doi.org/10.1371/journal.pone.0300648

Anselin, L., 1995. Local Indicators of Spatial Association—LISA. Geographical Analysis 27 (2), 93–115. https://doi.org/10.1111/j.1538-4632.1995.tb00338.x

Armbrust, M., Ghodsi, A., Xin, R., Zaharia, M., 2021. Lakehouse: a new generation of open platforms that unify data warehousing and advanced analytics. In: Proceedings of the 11th Conference on Innovative Data Systems Research (CIDR).

Bangladesh Bureau of Statistics, 2013–2025. Yearbook of Agricultural Statistics of Bangladesh, 2012–2024 editions (24th–36th series). Statistics and Informatics Division, Ministry of Planning, Dhaka.

Bangladesh Bureau of Statistics, 2026. Yearbook of Agricultural Statistics-2025 (37th series). Statistics and Informatics Division, Ministry of Planning, Dhaka.

Barker, M., Chue Hong, N.P., Katz, D.S., Lamprecht, A.-L., Martinez-Ortiz, C., Psomopoulos, F., Harrow, J., Castro, L.J., Gruenpeter, M., Martinez, P.A., et al., 2022. Introducing the FAIR Principles for research software. Scientific Data 9 (1), 622. https://doi.org/10.1038/s41597-022-01710-x

Benjamini, Y., Hochberg, Y., 1995. Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing. Journal of the Royal Statistical Society Series B: Statistical Methodology 57 (1), 289–300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x

Christen, P., 2012. Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection. Springer Berlin Heidelberg. https://doi.org/10.1007/978-3-642-31164-2

Copernicus Climate Change Service, 2019. ERA5-Land hourly data from 1950 to present [dataset]. Copernicus Climate Change Service (C3S) Climate Data Store (CDS). https://doi.org/10.24381/cds.e2161bac

Didan, K., 2021. MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061 [dataset]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MOD13Q1.061

Essawy, B.T., Goodall, J.L., Voce, D., Morsy, M.M., Sadler, J.M., Choi, Y.D., Tarboton, D.G., Malik, T., 2020. A taxonomy for reproducible and replicable research in environmental modelling. Environmental Modelling & Software 134, 104753. https://doi.org/10.1016/j.envsoft.2020.104753

Farr, T.G., Rosen, P.A., Caro, E., Crippen, R., Duren, R., Hensley, S., Kobrick, M., Paller, M., Rodriguez, E., Roth, L., et al., 2007. The Shuttle Radar Topography Mission. Reviews of Geophysics 45 (2), 2005RG000183. https://doi.org/10.1029/2005RG000183

GADM, 2022. Database of Global Administrative Areas, version 4.1 [dataset]. https://gadm.org.

Giuliani, G., Chatenoux, B., De Bono, A., Rodila, D., Richard, J.-P., Allenbach, K., Dao, H., Peduzzi, P., 2017. Building an Earth Observations Data Cube: lessons learned from the Swiss Data Cube (SDC) on generating Analysis Ready Data (ARD). Big Earth Data 1 (1-2), 100–117. https://doi.org/10.1080/20964471.2017.1398903

Gorelick, N., Hancher, M., Dixon, M., Ilyushchenko, S., Thau, D., Moore, R., 2017. Google Earth Engine: Planetary-scale geospatial analysis for everyone. Remote Sensing of Environment 202, 18–27. https://doi.org/10.1016/j.rse.2017.06.031

Graf, L.V., Perich, G., Aasen, H., 2022. EOdal: An open-source Python package for large-scale agroecological research using Earth Observation and gridded environmental data. Computers and Electronics in Agriculture 203, 107487. https://doi.org/10.1016/j.compag.2022.107487

Gregory, I.N., Ell, P.S., 2005. Breaking the Boundaries: Geographical Approaches to Integrating 200 Years of the Census. Journal of the Royal Statistical Society Series A: Statistics in Society 168 (2), 419–437. https://doi.org/10.1111/j.1467-985X.2005.00356.x

Hutton, C., Wagener, T., Freer, J., Han, D., Duffy, C., Arheimer, B., 2016. Most computational hydrology is not reproducible, so is it really science? Water Resources Research 52 (10), 7548–7555. https://doi.org/10.1002/2016WR019285

Iizumi, T., Sakai, T., 2020. The global dataset of historical yields for major crops 1981–2016. Scientific Data 7 (1), 97. https://doi.org/10.1038/s41597-020-0433-7

Iturbide, M., Bedia, J., Herrera, S., Baño-Medina, J., Fernández, J., Frías, M.D., Manzanas, R., San-Martín, D., Cimadevilla, E., Cofiño, A.S., et al., 2019. The R-based climate4R open framework for reproducible climate data access and post-processing. Environmental Modelling & Software 111, 42–54. https://doi.org/10.1016/j.envsoft.2018.09.009

Jagadish, S.V.K., Craufurd, P.Q., Wheeler, T.R., 2007. High temperature stress and spikelet fertility in rice (Oryza sativa L.). Journal of Experimental Botany 58 (7), 1627–1635. https://doi.org/10.1093/jxb/erm003

Janssen, S.J.C., Porter, C.H., Moore, A.D., Athanasiadis, I.N., Foster, I., Jones, J.W., Antle, J.M., 2017. Towards a new generation of agricultural system data, models and knowledge products: Information and communication technology. Agricultural Systems 155, 200–212. https://doi.org/10.1016/j.agsy.2016.09.017

Kallenberg, M., Paudel, D., Ofori-Ampofo, S., Baja, H., van Bree, R., Potze, A., Poudel, P., Saleh, A., Anderson, W., von Bloh, M., et al., 2026. CY-Bench: a comprehensive benchmark dataset for sub-national crop yield forecasting. Earth System Science Data 18 (6), 3997–4018. https://doi.org/10.5194/essd-18-3997-2026

Kamal, A.S.M.M., Shamsudduha, M., Ahmed, B., Hassan, S.M.K., Islam, M.S., Kelman, I., Fordham, M., 2018. Resilience to flash floods in wetland communities of northeastern Bangladesh. International Journal of Disaster Risk Reduction 31, 478–488. https://doi.org/10.1016/j.ijdrr.2018.06.011

Khidirova, E., Karakuş, O., 2026. UniCrop: A Universal, Multi-Source Data Engineering Pipeline for Scalable Crop Yield Prediction. arXiv preprint. https://doi.org/10.48550/arXiv.2601.01655

Konkol, M., Kray, C., Pfeiffer, M., 2019. Computational reproducibility in geoscientific papers: Insights from a series of studies with geoscientists and a reproduction study. International Journal of Geographical Information Science 33 (2), 408–429. https://doi.org/10.1080/13658816.2018.1508687

Landau, W., 2021. The targets R package: a dynamic Make-like function-oriented pipeline toolkit for reproducibility and high-performance computing. Journal of Open Source Software 6 (57), 2959. https://doi.org/10.21105/joss.02959

Lee, D., Anderson, W., Chen, X., Davenport, F., Shukla, S., Sahajpal, R., Budde, M., Rowland, J., Verdin, J., You, L., et al., 2025. HarvestStat Africa – Harmonized Subnational Crop Statistics for Sub-Saharan Africa. Scientific Data 12 (1), 690. https://doi.org/10.1038/s41597-025-05001-z

Lewis, A., Oliver, S., Lymburner, L., Evans, B., Wyborn, L., Mueller, N., Raevksi, G., Hooke, J., Woodcock, R., Sixsmith, J., et al., 2017. The Australian Geoscience Data Cube — Foundations and lessons learned. Remote Sensing of Environment 202, 276–292. https://doi.org/10.1016/j.rse.2017.03.015

Logan, J.R., Xu, Z., Stults, B.J., 2014. Interpolating U.S. Decennial Census Tract Data from as Early as 1970 to 2010: A Longitudinal Tract Database. The Professional Geographer 66 (3), 412–420. https://doi.org/10.1080/00330124.2014.905156

Mölder, F., Jablonski, K.P., Letcher, B., Hall, M.B., Tomkins-Tinch, C.H., Sochat, V., Forster, J., Lee, S., Twardziok, S.O., Kanitz, A., et al., 2021. Sustainable data analysis with Snakemake. F1000Research 10, 33. https://doi.org/10.12688/f1000research.29032.2

Moran, P.A.P., 1950. Notes on continuous stochastic phenomena. Biometrika 37 (1-2), 17–23. https://doi.org/10.1093/biomet/37.1-2.17

Muñoz-Sabater, J., Dutra, E., Agustí-Panareda, A., Albergel, C., Arduini, G., Balsamo, G., Boussetta, S., Choulga, M., Harrigan, S., Hersbach, H., et al., 2021. ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. Earth System Science Data 13 (9), 4349–4383. https://doi.org/10.5194/essd-13-4349-2021

Nüst, D., Granell, C., Hofer, B., Konkol, M., Ostermann, F.O., Sileryte, R., Cerutti, V., 2018. Reproducible research and GIScience: an evaluation using AGILE conference papers. PeerJ 6, e5072. https://doi.org/10.7717/peerj.5072

OECD, European Commission Joint Research Centre, 2008. Handbook on Constructing Composite Indicators: Methodology and User Guide. OECD Publishing, Paris. https://doi.org/10.1787/9789264043466-en

Paudel, D., Boogaard, H., de Wit, A., Janssen, S., Osinga, S., Pylianidis, C., Athanasiadis, I.N., 2021. Machine learning for large-scale crop yield forecasting. Agricultural Systems 187, 103016. https://doi.org/10.1016/j.agsy.2020.103016

Pekel, J.-F., Cottam, A., Gorelick, N., Belward, A.S., 2016. High-resolution mapping of global surface water and its long-term changes. Nature 540 (7633), 418–422. https://doi.org/10.1038/nature20584

Peng, R.D., 2011. Reproducible Research in Computational Science. Science 334 (6060), 1226–1227. https://doi.org/10.1126/science.1213847

Polyzotis, N., Roy, S., Whang, S.E., Zinkevich, M., 2018. Data Lifecycle Challenges in Production Machine Learning: A Survey. ACM SIGMOD Record 47 (2), 17–28. https://doi.org/10.1145/3299887.3299891

Prasad, P.V.V., Boote, K.J., Allen, L.H., Sheehy, J.E., Thomas, J.M.G., 2006. Species, ecotype and cultivar differences in spikelet fertility and harvest index of rice in response to high temperature stress. Field Crops Research 95 (2-3), 398–411. https://doi.org/10.1016/j.fcr.2005.04.008

Raasveldt, M., Mühleisen, H., 2019. DuckDB: an Embeddable Analytical Database. In: Proceedings of the 2019 International Conference on Management of Data, 1981–1984. https://doi.org/10.1145/3299869.3320212

Rahal, M., Ahmed, B.S., Samuelsson, J., 2023. Machine Learning Data Suitability and Performance Testing Using Fault Injection Testing Framework. arXiv preprint. https://doi.org/10.48550/arXiv.2309.11274

Rey, S.J., Anselin, L., 2007. PySAL: A Python Library of Spatial Analytical Methods. Review of Regional Studies 37 (1). https://doi.org/10.52324/001c.8285

Ronchetti, G., Nisini Scacchiafichi, L., Seguini, L., Cerrani, I., van der Velde, M., 2024. Harmonized European Union subnational crop statistics can reveal climate impacts and crop cultivation shifts. Earth System Science Data 16 (3), 1623–1649. https://doi.org/10.5194/essd-16-1623-2024

Runfola, D., Anderson, A., Baier, H., Crittenden, M., Dowker, E., Fuhrig, S., Goodman, S., Grimsley, G., Layko, R., Melville, G., et al., 2020. geoBoundaries: A global database of political administrative boundaries. PLOS ONE 15 (4), e0231866. https://doi.org/10.1371/journal.pone.0231866

Saisana, M., Saltelli, A., Tarantola, S., 2005. Uncertainty and Sensitivity Analysis Techniques as Tools for the Quality Assessment of Composite Indicators. Journal of the Royal Statistical Society Series A: Statistics in Society 168 (2), 307–323. https://doi.org/10.1111/j.1467-985X.2005.00350.x

Sandve, G.K., Nekrutenko, A., Taylor, J., Hovig, E., 2013. Ten Simple Rules for Reproducible Computational Research. PLOS Computational Biology 9 (10), e1003285. https://doi.org/10.1371/journal.pcbi.1003285

Sarkar, S.K., Rudra, R.R., Sohan, A.R., Das, P.C., Ekram, K.M.M., Talukdar, S., Rahman, A., Alam, E., Islam, M.K., Islam, A.R.M.T., 2023. Coupling of machine learning and remote sensing for soil salinity mapping in coastal area of Bangladesh. Scientific Reports 13 (1), 17056. https://doi.org/10.1038/s41598-023-44132-4

Schelter, S., Lange, D., Schmidt, P., Celikel, M., Biessmann, F., Grafberger, A., 2018. Automating large-scale data quality verification. Proceedings of the VLDB Endowment 11 (12), 1781–1794. https://doi.org/10.14778/3229863.3229867

Schramm, M., Pebesma, E., Milenković, M., Foresta, L., Dries, J., Jacob, A., Wagner, W., Mohr, M., Neteler, M., Kadunc, M., et al., 2021. The openEO API–Harmonising the Use of Earth Observation Cloud Services Using Virtual Data Cube Functionalities. Remote Sensing 13 (6), 1125. https://doi.org/10.3390/rs13061125

Shahrier, R., Hasan, M.N., Ankita, S.Y., Tasnim, I., Rahman, K.T., 2025. Impact of climate change on Boro rice production in Bangladesh: Evidence from time series modeling. PLOS ONE 20 (7), e0328699. https://doi.org/10.1371/journal.pone.0328699

Shamsudduha, M., Taylor, R.G., Longuevergne, L., 2012. Monitoring groundwater storage changes in the highly seasonal humid tropics: Validation of GRACE measurements in the Bengal Basin. Water Resources Research 48 (2), 2011WR010993. https://doi.org/10.1029/2011WR010993

Simmhan, Y.L., Plale, B., Gannon, D., 2005. A survey of data provenance in e-science. ACM SIGMOD Record 34 (3), 31–36. https://doi.org/10.1145/1084805.1084812

Stodden, V., McNutt, M., Bailey, D.H., Deelman, E., Gil, Y., Hanson, B., Heroux, M.A., Ioannidis, J.P.A., Taufer, M., 2016. Enhancing reproducibility for computational methods. Science 354 (6317), 1240–1241. https://doi.org/10.1126/science.aah6168

Tate, E., 2012. Social vulnerability indices: a comparative assessment using uncertainty and sensitivity analysis. Natural Hazards 63 (2), 325–347. https://doi.org/10.1007/s11069-012-0152-2

Torres, R., Snoeij, P., Geudtner, D., Bibby, D., Davidson, M., Attema, E., Potin, P., Rommen, B., Floury, N., Brown, M., et al., 2012. GMES Sentinel-1 mission. Remote Sensing of Environment 120, 9–24. https://doi.org/10.1016/j.rse.2011.05.028

Twele, A., Cao, W., Plank, S., Martinis, S., 2016. Sentinel-1-based flood mapping: a fully automated processing chain. International Journal of Remote Sensing 37 (13), 2990–3004. https://doi.org/10.1080/01431161.2016.1192304

Uddin, K., Matin, M.A., Meyer, F.J., 2019. Operational Flood Mapping Using Multi-Temporal Sentinel-1 SAR Images: A Case Study from Bangladesh. Remote Sensing 11 (13), 1581. https://doi.org/10.3390/rs11131581

Wang, R.Y., Strong, D.M., 1996. Beyond Accuracy: What Data Quality Means to Data Consumers. Journal of Management Information Systems 12 (4), 5–33. https://doi.org/10.1080/07421222.1996.11518099

Wilkinson, M.D., Dumontier, M., Aalbersberg, I.J., Appleton, G., Axton, M., Baak, A., Blomberg, N., Boiten, J.-W., da Silva Santos, L.B., Bourne, P.E., et al., 2016. The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data 3 (1), 160018. https://doi.org/10.1038/sdata.2016.18

Wilson, G., Bryan, J., Cranston, K., Kitzes, J., Nederbragt, L., Teal, T.K., 2017. Good enough practices in scientific computing. PLOS Computational Biology 13 (6), e1005510. https://doi.org/10.1371/journal.pcbi.1005510

Zanaga, D., Van De Kerchove, R., Daems, D., De Keersmaecker, W., Brockmann, C., Kirches, G., Wevers, J., Cartus, O., Santoro, M., Fritz, S., et al., 2022. ESA WorldCover 10 m 2021 v200 [dataset]. Zenodo. https://doi.org/10.5281/zenodo.7254221

Zhang, C., Di, L., Yang, Z., Lin, L., Hao, P., 2020. AgKit4EE: A toolkit for agricultural land use modeling of the conterminous United States based on Google Earth Engine. Environmental Modelling & Software 129, 104694. https://doi.org/10.1016/j.envsoft.2020.104694


# Appendix A. Software

Table A.1. Main software and versions used to produce the results (all packages are pinned in requirements-lock.txt).

| Package | Version | Role |
|------------------|-----------|--------------------------|
| Python | 3.13.7 | Language |
| duckdb | 1.5.2 | Analytical warehouse (Gold layer) |
| pandas | 2.3.3 | Data manipulation |
| numpy | 2.3.3 | Numerics |
| pyarrow | 24.0.0 | Parquet (Silver layer) |
| camelot-py | 1.0.9 | BBS PDF table extraction |
| earthengine-api | 1.7.22 | MODIS, ERA5-Land, JRC, Sentinel-1 extraction |
| geopandas | 1.1.3 | Boundaries and maps |
| libpysal | 4.14.1 | Spatial weights |
| esda | 2.9.0 | Moran's I, LISA |
| statsmodels | 0.14.6 | FDR correction |
| scipy | 1.16.3 | Rank correlations |
| matplotlib | 3.10.7 | Figures |
| streamlit | 1.58.0 | Dashboard |
| plotly | 6.8.0 | Dashboard charts |

# Appendix B. Example application: vulnerability index and spatial clustering

## B.1 Method

A district vulnerability index combines five components computed from the Gold tables, each min–max normalised across districts so that higher values mean greater vulnerability (Table B.1). Two describe the sensitivity of Boro production and three describe exposure. Production instability is measured on production rather than yield because BBS yield is reported per harvested hectare, so a crop destroyed before harvest lowers harvested area and production but not reported yield (Section 6.7). The flood components use the JRC series over harvest years 2011–2021, the longest period in which both JRC flood variables exist for every district, so that all districts are compared over the same years with one sensor; Sentinel-1 begins only in 2015 (flash) and 2016 (monsoon). Equal weights are used as the baseline because there is no agreed basis for preferring one component over another (OECD and European Commission Joint Research Centre, 2008). Weight sensitivity is assessed by omitting each component in turn and by drawing 10,000 weight vectors uniformly from the simplex and recording, for each district, the share of draws in which it ranks in the top ten (Saisana et al., 2005; Tate, 2012).

Table B.1. Vulnerability index components (all computed from observed data).

| Component | Definition | Period |
|---|---|---|
| Low yield | Negative of mean BBS Boro yield | 2011–2025 |
| Production instability | Standard deviation of linearly detrended log BBS production | 2011–2025 |
| Monsoon flood exposure | Mean JRC monsoon flood fraction (inundation extent before planting) | 2011–2021 |
| Flash flood exposure | Mean JRC flash flood fraction (inundation extent in the harvest window) | 2011–2021 |
| Heat exposure | Mean number of hot days (Tmax > 35 °C, March–May) | 2011–2025 |

Spatial weights use fuzzy contiguity: districts are neighbours if their boundaries, buffered by 100 m, touch, which avoids spurious islands caused by slivers between GADM polygons. Weights are row-standardised. Global Moran's I (Moran, 1950) is tested with 9,999 random permutations, so the smallest attainable pseudo p-value is 0.0001. Local indicators of spatial association (LISA) (Anselin, 1995) classify districts at pseudo p < 0.05, and clusters that survive a Benjamini–Hochberg false discovery rate (FDR) correction across the 64 tests are also reported (Benjamini and Hochberg, 1995). Because a stable ranking does not imply a stable spatial pattern, the spatial analysis was repeated for the first 1,000 of the random weight vectors: for each, global Moran's I and LISA were recomputed (999 permutations each), recording the share of weightings with significant global autocorrelation and, for each district, the share in which it is classified high–high at pseudo p < 0.05 and after FDR correction. Spatial statistics were computed with the PySAL libraries libpysal and esda (Rey and Anselin, 2007); permutation tests use fixed random seeds.

## B.2 Results

The index ranges from 0.104 (Noakhali) to 0.578 (Sunamganj). The ten highest-ranked districts (Table B.2) fall into three groups: north-eastern districts in and near the haor basin (Sunamganj, Kishoreganj, Sylhet, Brahmanbaria, Habiganj, Netrokona), where flood exposure is high; the coastal districts Patuakhali and Barguna, where low yields and unstable production on a small Boro area dominate; and western districts (Chapai Nawabganj, Meherpur), where heat exposure dominates. Across 10,000 random weight vectors, the median Spearman correlation with the equal-weight ranking is 0.80 (5th percentile 0.51), and 9 of the ten top-ranked districts remain in the top ten in at least half of the draws; the exception is Meherpur (47 %). Omitting one component at a time gives Spearman correlations of 0.60–0.97 with the baseline.

Table B.2. The ten highest-ranked districts. Flood columns are mean JRC fractions (2011–2021); the top-10 share is the percentage of 10,000 random weightings in which the district ranks in the top ten; LISA is the baseline classification at pseudo p < 0.05; the HH share is the percentage of 1,000 random weightings in which the district is classified high–high.

| Rank | District | Index | Yield (t/ha) | Monsoon flood (%) | Flash flood (%) | Hot days | Top-10 share (%) | LISA | HH share (%) |
|--------|-------------------|---------|----------|-----------|---------|--------|----------|--------|---------|
| 1 | Sunamganj | 0.578 | 3.79 | 48.2 | 16.4 | 1.9 | 88 | HH | 65 |
| 2 | Patuakhali | 0.464 | 2.67 | 2.5 | 0.9 | 7.6 | 77 | ns | 15 |
| 3 | Kishoreganj | 0.460 | 4.23 | 46.6 | 12.7 | 6.7 | 77 | HH | 49 |
| 4 | Barguna | 0.368 | 3.06 | 1.0 | 0.5 | 7.0 | 61 | ns | 26 |
| 5 | Sylhet | 0.354 | 3.07 | 21.3 | 7.2 | 1.6 | 70 | HH | 67 |
| 6 | Brahmanbaria | 0.318 | 4.04 | 30.1 | 4.3 | 8.9 | 56 | ns | 9 |
| 7 | Chapai Nawabganj | 0.307 | 4.08 | 11.0 | 0.1 | 25.8 | 51 | ns | 3 |
| 8 | Habiganj | 0.306 | 3.66 | 18.7 | 6.2 | 6.2 | 59 | HH | 74 |
| 9 | Netrokona | 0.304 | 4.15 | 28.9 | 7.2 | 4.1 | 53 | HH | 62 |
| 10 | Meherpur | 0.303 | 4.00 | 0.6 | 0.0 | 29.9 | 47 | ns | 22 |

With equal weights, the index is spatially clustered (global Moran's I = 0.429, z = 5.54, pseudo p = 0.0001, the minimum attainable with 9,999 permutations). LISA identifies a high–high cluster of five north-eastern districts (Sunamganj, Kishoreganj, Sylhet, Habiganj, Netrokona) and low–low clusters in the north-west and the lower Meghna region (Fig. 4); after FDR correction, Sunamganj and Habiganj remain significant high–high districts and Nilphamari a significant low–low district. Under alternative weights, global Moran's I is significant in 100 % of the 1,000 weightings (median I = 0.49; 90 % of values between 0.29 and 0.63). Each of the five baseline high–high districts is classified high–high in 49–74 % of weightings (24–44 % after FDR correction), more often than any other district (next: Kushtia, 32 %); weightings that emphasise heat exposure produce a smaller high–high group in the west instead.

# Appendix C. From parsed BBS rows to the panel

Table C.1. Accounting from the district rows parsed in the 14 yearbook editions to the district-years of the panel.

| Step | Count | Notes |
|--------------------------|---------|--------------------------|
| Edition–crop-year tables located | 28 | 14 editions, two crop years each |
| District rows possible | 1,792 | 64 per table |
| District rows parsed | 1,726 | 66 not parsed: Tangail in both crop years of the 2015 edition; 32 districts in both crop years of the 2018 edition |
| Rows failing a unit identity (excluded) | 4 | 2013 edition, crop year 2012-13; yield identity |
| Rows accepted | 1,722 |  |
| District-year pairs printed in two editions | 832 | crop years 2011-12 to 2023-24, 64 districts each |
| Pairs with a parsed row in both editions (compared) | 766 | compared on area (ha) and yield (t/ha) |
| Compared pairs that differ | 6 | each by at most 1 ha of area |
| District-years in the panel | 960 | later edition used where both editions have an accepted row |
|   from the earlier edition (later row missing or failed) | 33 |  |
|   from a crop year printed in one edition only | 128 | 2010-11 (2012 edition), 2024-25 (2025 edition) |
|   from single-district region rows | 10 | 2012 and 2013 editions; region-to-district equivalence verified on crop year 2012-13 against the 2014 edition |

Table C.2. Single-district region rows of the 2013 edition compared with the district rows printed for the same crop year (2012-13) in the 2014 edition.

| Region row (2013 edition, 2012-13) | Area (ha) | Production (t) | District row (2014 edition, 2012-13) | Area (ha)  | Production (t)  |
|---------------------|----------|--------------|---------------|----------|--------------|
| Bandarban Region | 3,227 | 9,650 | Bandarban | 3,227 | 9,650 |
| Khagrachari Region | 10,272 | 33,326 | Khagrachhari | 10,272 | 33,326 |
| Rangamati Region | 4,788 | 16,623 | Rangamati | 4,788 | 16,623 |
| Mymenshing Region | 262,040 | 936,015 | Mymensingh | 262,040 | 936,015 |
| Tangail Region | 163,636 | 658,469 | Tangail | 163,636 | 658,469 |

# Appendix D. Descriptive statistics of the integrated panel

Table D.1. Descriptive statistics of the integrated panel (district-year observations).

| Variable | Harvest years | N | Mean | SD | Min | Max |
|--------------------------|------------|------|---------|---------|---------|----------|
| Boro yield (t/ha, husked rice) | 2011–2025 | 960 | 4.014 | 0.448 | 2.083 | 5.375 |
| Boro area (ha) | 2011–2025 | 960 | 74,844 | 57,574 | 230 | 266,243 |
| Peak-season NDVI (Jan–Apr) | 2011–2025 | 960 | 0.534 | 0.047 | 0.342 | 0.631 |
| Mean temperature (°C) | 2011–2025 | 960 | 23.448 | 0.838 | 21.305 | 25.584 |
| Mean daily maximum temperature (°C) | 2011–2025 | 960 | 28.661 | 0.742 | 26.662 | 30.774 |
| Season precipitation (mm) | 2011–2025 | 960 | 539 | 253 | 119 | 2,165 |
| Hot days, Tmax > 35 °C (Mar–May) | 2011–2025 | 960 | 13.502 | 12.482 | 0.000 | 51.328 |
| Monsoon flood fraction, JRC | 2011–2022 | 768 | 0.078 | 0.101 | 0.000 | 0.646 |
| Flash flood fraction, JRC | 2011–2021 | 704 | 0.014 | 0.042 | 0.000 | 0.439 |
| Monsoon flood fraction, Sentinel-1 | 2016–2025 | 640 | 0.083 | 0.103 | 0.000 | 0.646 |
| Flash flood fraction, Sentinel-1 | 2015–2025 | 704 | 0.014 | 0.032 | 0.000 | 0.447 |
