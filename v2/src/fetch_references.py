"""Fetch bibliographic metadata for the EMS manuscript from Crossref/DataCite
(by DOI) so author lists, years and pages come from the registries.
Entries without a DOI are given manually.  Output: v2/paper_ems/references.json
"""
import json
import time
import urllib.request

from common import V2

OUT = V2 / "paper_ems" / "references.json"
UA = {"User-Agent": "bangladesh-agri-ref-check (mailto:tasnimmumu414@gmail.com)"}

DOIS = {
    "wilkinson2016": "10.1038/sdata.2016.18",
    "shahrier2025": "10.1371/journal.pone.0328699",
    "almamun2024": "10.1371/journal.pone.0300648",
    "khidirova2026": "10.48550/arXiv.2601.01655",
    "kallenberg2026": "10.5194/essd-18-3997-2026",
    "lee2025": "10.1038/s41597-025-05001-z",
    "ronchetti2024": "10.5194/essd-16-1623-2024",
    "iizumi2020": "10.1038/s41597-020-0433-7",
    "zhang2020": "10.1016/j.envsoft.2020.104694",
    "iturbide2019": "10.1016/j.envsoft.2018.09.009",
    "graf2022": "10.1016/j.compag.2022.107487",
    "tate2012": "10.1007/s11069-012-0152-2",
    "kamal2018": "10.1016/j.ijdrr.2018.06.011",
    "pekel2016": "10.1038/nature20584",
    "uddin2019": "10.3390/rs11131581",
    "didan2021": "10.5067/MODIS/MOD13Q1.061",
    "gorelick2017": "10.1016/j.rse.2017.06.031",
    "zanaga2022": "10.5281/zenodo.7254221",
    "munozsabater2021": "10.5194/essd-13-4349-2021",
    "torres2012": "10.1016/j.rse.2011.05.028",
    "farr2007": "10.1029/2005RG000183",
    "raasveldt2019": "10.1145/3299869.3320212",
    "jagadish2007": "10.1093/jxb/erm003",
    "prasad2006": "10.1016/j.fcr.2005.04.008",
    "twele2016": "10.1080/01431161.2016.1192304",
    "saisana2005": "10.1111/j.1467-985X.2005.00350.x",
    "moran1950": "10.1093/biomet/37.1-2.17",
    "anselin1995": "10.1111/j.1538-4632.1995.tb00338.x",
    "benjamini1995": "10.1111/j.2517-6161.1995.tb02031.x",
    "rey2007": "10.52324/001c.8285",
    "shamsudduha2012": "10.1029/2011WR010993",
    "sarkar2023": "10.1038/s41598-023-44132-4",
    # Related work: reproducibility, data validation, provenance, harmonisation
    "barker2022": "10.1038/s41597-022-01710-x",
    "sandve2013": "10.1371/journal.pcbi.1003285",
    "wilson2017": "10.1371/journal.pcbi.1005510",
    "peng2011": "10.1126/science.1213847",
    "stodden2016": "10.1126/science.aah6168",
    "hutton2016": "10.1002/2016WR019285",
    "konkol2019": "10.1080/13658816.2018.1508687",
    "nust2018": "10.7717/peerj.5072",
    "essawy2020": "10.1016/j.envsoft.2020.104753",
    "schelter2018": "10.14778/3229863.3229867",
    "polyzotis2018": "10.1145/3299887.3299891",
    "wang1996": "10.1080/07421222.1996.11518099",
    "simmhan2005": "10.1145/1084805.1084812",
    "runfola2020": "10.1371/journal.pone.0231866",
    "christen2012": "10.1007/978-3-642-31164-2",
    "gregory2005": "10.1111/j.1467-985X.2005.00356.x",
    "logan2014": "10.1080/00330124.2014.905156",
    "paudel2021": "10.1016/j.agsy.2020.103016",
    "janssen2017": "10.1016/j.agsy.2016.09.017",
    "lewis2017": "10.1016/j.rse.2017.03.015",
    "giuliani2017": "10.1080/20964471.2017.1398903",
    "schramm2021": "10.3390/rs13061125",
    "molder2021": "10.12688/f1000research.29032.2",
    "landau2021": "10.21105/joss.02959",
    "rahal2023": "10.48550/arXiv.2309.11274",
}

MANUAL = {
    "bbs2026": dict(type="report", authors=[{"family": "Bangladesh Bureau of Statistics", "given": ""}],
                    year=2026, title="Yearbook of Agricultural Statistics-2025 (37th series)",
                    publisher="Statistics and Informatics Division, Ministry of Planning, Dhaka"),
    "bbs2013": dict(type="report", authors=[{"family": "Bangladesh Bureau of Statistics", "given": ""}],
                    year="2013–2025", title="Yearbook of Agricultural Statistics of Bangladesh, 2012–2024 editions (24th–36th series)",
                    publisher="Statistics and Informatics Division, Ministry of Planning, Dhaka"),
    "armbrust2021": dict(type="paper-conference",
                         authors=[{"family": "Armbrust", "given": "Michael"}, {"family": "Ghodsi", "given": "Ali"},
                                  {"family": "Xin", "given": "Reynold"}, {"family": "Zaharia", "given": "Matei"}],
                         year=2021, title="Lakehouse: a new generation of open platforms that unify data warehousing and advanced analytics",
                         container="Proceedings of the 11th Conference on Innovative Data Systems Research (CIDR)"),
    "oecd2008": dict(type="book", authors=[{"family": "OECD", "given": ""}, {"family": "European Commission Joint Research Centre", "given": ""}],
                     year=2008, title="Handbook on Constructing Composite Indicators: Methodology and User Guide",
                     publisher="OECD Publishing, Paris", doi="10.1787/9789264043466-en"),
    "gadm2022": dict(type="dataset", authors=[{"family": "GADM", "given": ""}], year=2022,
                     title="Database of Global Administrative Areas, version 4.1", publisher="https://gadm.org"),
}


# Registry titles that need correcting (e.g. a journal running head stored as a subtitle)
TITLE_FIX = {"hutton2016": "Most computational hydrology is not reproducible, so is it really science?"}


def get(url):
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception:
            time.sleep(3)
    raise RuntimeError(url)


def crossref(doi):
    m = get(f"https://api.crossref.org/works/{doi}")["message"]
    return dict(type=m.get("type"), doi=doi,
                authors=[{"family": a.get("family") or a.get("name", ""), "given": a.get("given", "")}
                         for a in m.get("author", [])],
                # year of the printed issue where there is one (volume year), else first publication
                year=((m.get("published-print") or m.get("issued") or {}).get("date-parts") or [[None]])[0][0],
                title=": ".join(x for x in [(m.get("title") or [""])[0], (m.get("subtitle") or [""])[0]] if x),
                container=(m.get("container-title") or [""])[0],
                volume=m.get("volume"), issue=m.get("issue"),
                pages=m.get("article-number") or m.get("page"), publisher=m.get("publisher"))


def datacite(doi):
    a = get(f"https://api.datacite.org/dois/{doi}")["data"]["attributes"]
    au = []
    for c in a["creators"]:
        fam = c.get("familyName") or c.get("name", "").split(",")[0]
        au.append({"family": fam.strip(), "given": (c.get("givenName") or "").strip()})
    return dict(type=a["types"].get("resourceTypeGeneral", "Dataset").lower(), doi=doi, authors=au,
                year=a["publicationYear"], title=a["titles"][0]["title"],
                publisher=a.get("publisher") if isinstance(a.get("publisher"), str) else (a.get("publisher") or {}).get("name"))


def main():
    refs = dict(MANUAL)
    for key, doi in DOIS.items():
        try:
            refs[key] = crossref(doi)
        except RuntimeError:
            refs[key] = datacite(doi)
        if key in TITLE_FIX:
            refs[key]["title"] = TITLE_FIX[key]
        print(f"{key:18s} {refs[key]['year']}  {', '.join(a['family'] for a in refs[key]['authors'][:3])}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(refs, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
