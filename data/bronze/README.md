# Downloaded inputs

The pipeline reads two inputs that are not redistributed with the code.
Download them and place them here before running `python v2/run_all.py`.

| Folder | Files | Source |
|---|---|---|
| `bbs/pdfs/` | `bbs_agri_yearbook_<edition>.pdf` for the 2012–2025 editions (e.g. `bbs_agri_yearbook_2025.pdf`) | Yearbook of Agricultural Statistics, Bangladesh Bureau of Statistics (bbs.gov.bd) |
| `gadm_shapefiles/` | `gadm41_BGD_0.*` and `gadm41_BGD_2.*`, unzipped from `gadm41_BGD_shp.zip` | GADM v4.1 (gadm.org); the licence does not permit redistribution |

`v2/data/bronze/manifest.csv` lists the SHA-256 of each file used. The
pipeline rewrites the manifest on every run, so after a run
`git diff v2/data/bronze/manifest.csv` is empty if your downloads are the
files used, and shows the rows of any file that differs.

The satellite and climate extracts are not needed from here: they are
included in `v2/data/bronze/gee/`.
