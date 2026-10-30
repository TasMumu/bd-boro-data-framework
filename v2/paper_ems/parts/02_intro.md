# 1. Introduction

Agricultural monitoring increasingly combines government crop statistics with satellite observations and climate reanalysis. These sources arrive on different schedules, in different formats and at different spatial resolutions. Official statistics are often published only as tables in PDF reports, administrative units are spelled differently from one source to the next, and a crop season may span two calendar years. The steps that join such sources (table extraction, name matching, temporal alignment and quality control) can introduce errors that leave a dataset with the expected shape but the wrong values: a misread cell, a district matched to its neighbour, or a yield paired with the previous season's weather. Such errors propagate silently into every downstream model.

Computational reproducibility is widely advocated [@peng2011; @sandve2013; @wilson2017; @stodden2016] and is part of the FAIR principles for research data and software [@wilkinson2016; @barker2022], yet attempts to reproduce published results in hydrology and the geosciences often fail [@hutton2016; @konkol2019; @nust2018]. For data integration pipelines, sharing code and data is necessary but not sufficient. Users also need evidence that the quality checks would detect the errors they are meant to detect, and that the outputs can be rebuilt from the documented inputs in a new installation. Such evidence is rarely reported.

Bangladesh is a demanding test case. The irrigated dry-season Boro crop supplies a little over half of national rice production; BBS estimates Boro output at 21.3 million tonnes of husked rice in 2024-25 [@bbs2026]. District statistics are published each year in the Bangladesh Bureau of Statistics (BBS) Yearbook of Agricultural Statistics as PDF tables whose layout, district spellings and regional groupings change between editions [@bbs2013; @bbs2026]. Floods affect the crop through monsoon inundation before planting and through pre-harvest flash floods, and the two available satellite flood records cover different periods.

This paper presents an open data engineering framework that integrates BBS district Boro statistics with satellite, flood and climate data for all 64 districts of Bangladesh, and evaluates it against four questions:

- Q1. How completely, and how transparently, are district names harmonised across sources?
- Q2. Do the validation checks detect structural, relational, temporal, value, geographic, cross-source and lineage errors, and does the pipeline stop when an input is wrong?
- Q3. Are the outputs reproducible when the pipeline is rebuilt, including from a clean installation?
- Q4. What does it cost to run the pipeline, and what changes are needed to add a season or a source?

The contributions are:

- a Bronze–Silver–Gold pipeline in Python and DuckDB with a single schema specification, a district crosswalk with stable identifiers, explicit harvest-year alignment and value-level provenance;
- validation methods for official statistics published as PDF tables, which exploit the redundancy within the publications (units printed twice, national totals, years printed in two editions, regional groupings) in addition to generic schema, key and range checks;
- an evaluation of the framework with matching metrics, deliberately corrupted inputs, rebuilds in two clean environments with explicit comparison rules, and measured run times, all scripted so that they can be rerun;
- an open panel of {{ R['n_panel'] }} BBS district-years (64 districts, harvest years 2011–2025) in which every value is traceable to a yearbook edition and page, with satellite and climate covariates for their source periods.

Section 2 reviews related work, Section 3 describes the study context and data sources, Section 4 the framework design and Section 5 the evaluation methodology. Section 6 reports the results in the order of the evaluation, Section 7 discusses what the evaluation does and does not establish, and Section 8 concludes.
