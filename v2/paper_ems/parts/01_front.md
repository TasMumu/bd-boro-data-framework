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

Official crop statistics are often combined with satellite and climate data, but the integration is seldom tested. We present an open Python and DuckDB framework that extracts district Boro rice statistics from 14 Bangladesh Bureau of Statistics yearbooks, harmonises district names, and aligns the statistics by harvest year with cropland NDVI, ERA5-Land climate and two flood records. We evaluated it with matching metrics, a validation report, corrupted inputs and clean-environment rebuilds. All {{ f"{EVS['records']:,}" }} source records, in {{ EVS['spellings'] }} distinct spellings, matched 64 districts; for every crop year, district sums matched the published national total (from the yearbook text where tables print none); the validation report raised no failures; each of {{ w(EVS['corrupt']) }} corrupted inputs stopped the pipeline with a diagnostic naming the failed check and the affected file, column or record; and in {{ w(EVS['envs']) }} fresh installations all {{ EVS['generated'] }} generated outputs matched the reference under stated rules. Code and derived data are open.

**Keywords:** data engineering; data validation; reproducibility; agricultural statistics; Sentinel-1; Bangladesh

# Software and data availability

- Name: bd-boro-data-framework
- Developer and contact: Tasnim Ahmad Mumu, University of Rajshahi; tasnimmumu414@gmail.com
- Year first available: 2026
- Hardware required: a standard desktop or laptop computer (tested on {{ T['machine']['os'] }} with {{ T['machine']['cpus'] }} logical CPUs and {{ T['machine']['ram_gb'] }} GB RAM)
- Software required: Python 3.11 or later (tested with {{ T['machine']['python'] }}) and the packages pinned in requirements-lock.txt (main packages in Appendix A); a Google Earth Engine account is needed only to re-extract satellite and climate data, since the extracts are included; pandoc is needed only to rebuild the manuscript
- Programming languages: Python and SQL (DuckDB)
- Documentation: README, a data dictionary generated from the specification, and two Jupyter notebooks (v2/notebooks) that build the dataset from the original sources step by step and document its evaluation
- Program size: {{ f"{CODE['lines']:,}" }} lines of code ({{ CODE['kb'] }} KB), plus the test scripts
- Availability: https://github.com/TasMumu/bd-boro-data-framework (folder v2); the version described here is archived on Zenodo at https://doi.org/10.5281/zenodo.23795046
- Licence and cost: free of charge. The code is released under the MIT licence. The derived data in the repository remain subject to the terms of the sources they are derived from (Table 2); the MIT licence does not apply to them
- Data: the repository contains the derived data: the validated BBS district panel with the edition and page of every value, the Earth Engine district extracts, the district crosswalk, the validation report and the DuckDB analytical database. The BBS yearbook PDFs and the GADM boundaries are not redistributed and must be obtained from their publishers; the README explains how, and how to confirm from the SHA-256 checksums in the manifest that they are the files used.
