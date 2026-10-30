# 8. Conclusions

This paper presented and evaluated an open Bronze–Silver–Gold data engineering framework, implemented in Python and DuckDB, that integrates official BBS district Boro statistics with satellite, flood and climate data for all 64 districts of Bangladesh. Every one of the {{ R['n_panel'] }} district-year values is read from a printed BBS table, checked against unit identities, reconciled with the national total and with a second edition where one exists, assigned to a present-day district and aligned to the Boro harvest year; no value is imputed. The evaluation showed that all {{ f"{EVS['records']:,}" }} district records across the sources were matched to the 64 districts through published rules, that the validation report raised no failures, that each of {{ w(EVS['corrupt']) }} deliberately corrupted inputs stopped the pipeline with a diagnostic naming the problem, and that in {{ w(EVS['envs']) }} clean environments every generated output matched the reference under explicit comparison rules, with byte-level differences confined to file containers, folder paths and run times. The evidence has stated limits: it concerns the extraction and integration, not the accuracy of the survey estimates or of the satellite variables, and the fresh-setup test used local copies of the inputs on one computer. What can be reused is the combination of value-level checks of digitised statistics, explicit name harmonisation, declared temporal alignment, provenance for every value, and scripted tests that show the checks work. The code and the derived data, including the crosswalk, the validation report and the analytical warehouse, are openly available, the BBS yearbooks and GADM boundaries can be obtained from their publishers, and the pipeline and its tests can be rerun with single commands.

# CRediT authorship contribution statement

Tasnim Ahmad Mumu: Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Writing – original draft, Writing – review & editing, Visualization. Rezaul Karim: Supervision, Methodology, Validation, Writing – review & editing.

# Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

# Declaration of competing interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

# Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the authors used Claude (Anthropic) to assist with code development, data validation and analysis scripts, and drafting and editing of the manuscript text. After using this tool, the authors reviewed and edited the content as needed and take full responsibility for the content of the published article.

# Data availability

The code (MIT licence) and the derived data are available in the repository given in the Software and data availability section; the derived data remain subject to the terms of their sources (Table 2). The BBS yearbook PDFs and the GADM v4.1 boundaries are not redistributed and must be obtained from the Bangladesh Bureau of Statistics and gadm.org; the manifest in the repository lists the SHA-256 checksum of each file used.
