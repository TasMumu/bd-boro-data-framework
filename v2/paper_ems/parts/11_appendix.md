# Appendix A. Software

Table A.1. Main software and versions used to produce the results (all packages are pinned in requirements-lock.txt).

{{ table_software_ems }}

# Appendix B. Example application: vulnerability index and spatial clustering

## B.1 Method

A district vulnerability index combines five components computed from the Gold tables, each min–max normalised across districts so that higher values mean greater vulnerability (Table B.1). Two describe the sensitivity of Boro production and three describe exposure. Production instability is measured on production rather than yield because BBS yield is reported per harvested hectare, so a crop destroyed before harvest lowers harvested area and production but not reported yield (Section 6.7). The flood components use the JRC series over harvest years 2011–2021, the longest period in which both JRC flood variables exist for every district, so that all districts are compared over the same years with one sensor; Sentinel-1 begins only in 2015 (flash) and 2016 (monsoon). Equal weights are used as the baseline because there is no agreed basis for preferring one component over another [@oecd2008]. Weight sensitivity is assessed by omitting each component in turn and by drawing 10,000 weight vectors uniformly from the simplex and recording, for each district, the share of draws in which it ranks in the top ten [@saisana2005; @tate2012].

Table B.1. Vulnerability index components (all computed from observed data).

| Component | Definition | Period |
|---|---|---|
| Low yield | Negative of mean BBS Boro yield | 2011–2025 |
| Production instability | Standard deviation of linearly detrended log BBS production | 2011–2025 |
| Monsoon flood exposure | Mean JRC monsoon flood fraction (inundation extent before planting) | 2011–2021 |
| Flash flood exposure | Mean JRC flash flood fraction (inundation extent in the harvest window) | 2011–2021 |
| Heat exposure | Mean number of hot days (Tmax > 35 °C, March–May) | 2011–2025 |

Spatial weights use fuzzy contiguity: districts are neighbours if their boundaries, buffered by 100 m, touch, which avoids spurious islands caused by slivers between GADM polygons. Weights are row-standardised. Global Moran's I [@moran1950] is tested with 9,999 random permutations, so the smallest attainable pseudo p-value is 0.0001. Local indicators of spatial association (LISA) [@anselin1995] classify districts at pseudo p < 0.05, and clusters that survive a Benjamini–Hochberg false discovery rate (FDR) correction across the 64 tests are also reported [@benjamini1995]. Because a stable ranking does not imply a stable spatial pattern, the spatial analysis was repeated for the first 1,000 of the random weight vectors: for each, global Moran's I and LISA were recomputed (999 permutations each), recording the share of weightings with significant global autocorrelation and, for each district, the share in which it is classified high–high at pseudo p < 0.05 and after FDR correction. Spatial statistics were computed with the PySAL libraries libpysal and esda [@rey2007]; permutation tests use fixed random seeds.

## B.2 Results

The index ranges from {{ f(R['vi']['min'][1]) }} ({{ R['vi']['min'][0] }}) to {{ f(R['vi']['max'][1]) }} ({{ R['vi']['max'][0] }}). The ten highest-ranked districts (Table B.2) fall into three groups: north-eastern districts in and near the haor basin (Sunamganj, Kishoreganj, Sylhet, Brahmanbaria, Habiganj, Netrokona), where flood exposure is high; the coastal districts Patuakhali and Barguna, where low yields and unstable production on a small Boro area dominate; and western districts (Chapai Nawabganj, Meherpur), where heat exposure dominates. Across 10,000 random weight vectors, the median Spearman correlation with the equal-weight ranking is {{ f(R['vi']['random_weights']['spearman_median'], 2) }} (5th percentile {{ f(R['vi']['random_weights']['spearman_p05'], 2) }}), and {{ int((TOP.p_top10_random_weights >= 0.5).sum()) }} of the ten top-ranked districts remain in the top ten in at least half of the draws; the exception is {{ ", ".join(f"{d} ({100 * s:.0f} %)" for d, s in TOP.p_top10_random_weights[TOP.p_top10_random_weights < 0.5].items()) }}. Omitting one component at a time gives Spearman correlations of {{ f(min(v['spearman'] for v in R['vi']['leave_one_out'].values()), 2) }}–{{ f(max(v['spearman'] for v in R['vi']['leave_one_out'].values()), 2) }} with the baseline.

Table B.2. The ten highest-ranked districts. Flood columns are mean JRC fractions (2011–2021); the top-10 share is the percentage of 10,000 random weightings in which the district ranks in the top ten; LISA is the baseline classification at pseudo p < 0.05; the HH share is the percentage of 1,000 random weightings in which the district is classified high–high.

{{ table_vi_top }}

With equal weights, the index is spatially clustered (global Moran's I = {{ f(R['vi']['moran_I']) }}, z = {{ f(R['vi']['moran_z'], 2) }}, pseudo p = {{ f(R['vi']['moran_p'], 4) }}, the minimum attainable with 9,999 permutations). LISA identifies a high–high cluster of {{ w(len(R['vi']['hh_005'])) }} north-eastern districts ({{ ", ".join(R['vi']['hh_005']) }}) and low–low clusters in the north-west and the lower Meghna region (Fig. 4); after FDR correction, {{ " and ".join(R['vi']['hh_fdr']) }} remain significant high–high districts and {{ " and ".join(R['vi']['ll_fdr']) }} a significant low–low district. Under alternative weights, global Moran's I is significant in {{ f(100 * HH['share_global_sig'], 0) }} % of the {{ f"{HH['draws']:,}" }} weightings (median I = {{ f(HH['moran_I_median'], 2) }}; 90 % of values between {{ f(HH['moran_I_p05'], 2) }} and {{ f(HH['moran_I_p95'], 2) }}). Each of the {{ w(HH['n']) }} baseline high–high districts is classified high–high in {{ f(HH['min'], 0) }}–{{ f(HH['max'], 0) }} % of weightings ({{ f(HH['fdr_min'], 0) }}–{{ f(HH['fdr_max'], 0) }} % after FDR correction), more often than any other district (next: {{ HH['other_name'] }}, {{ f(HH['other_max'], 0) }} %); weightings that emphasise heat exposure produce a smaller high–high group in the west instead.

# Appendix C. From parsed BBS rows to the panel

Table C.1. Accounting from the district rows parsed in the 14 yearbook editions to the district-years of the panel.

{{ table_bbs_flow }}

Table C.2. Single-district region rows of the 2013 edition compared with the district rows printed for the same crop year (2012-13) in the 2014 edition.

{{ table_region_checks }}

# Appendix D. Descriptive statistics of the integrated panel

Table D.1. Descriptive statistics of the integrated panel (district-year observations).

{{ table_descriptives }}
