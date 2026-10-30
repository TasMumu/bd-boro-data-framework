"""Shared paths and helpers for the v2 (BBS-only) pipeline."""
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]          # project root
# The working data/output folder can be redirected (used by the failure tests
# so that they never touch the real data); defaults to the v2 folder.
V2 = Path(os.environ.get("BD_AGRI_V2_DIR", ROOT / "v2"))
BRONZE = ROOT / "data" / "bronze"
V2_BRONZE = V2 / "data" / "bronze"
V2_SILVER = V2 / "data" / "silver"
V2_GOLD = V2 / "data" / "gold" / "bangladesh_agri_v2.duckdb"
TABLES = V2 / "outputs" / "tables"
FIGURES = V2 / "outputs" / "figures"
LOGS = V2 / "logs"

for p in (V2_BRONZE, V2_SILVER, V2_GOLD.parent, TABLES, FIGURES, LOGS):
    p.mkdir(parents=True, exist_ok=True)

GEE_PROJECT = "bd-agri-climate"

# Canonical district names (64) and the spelling variants found across
# BBS yearbooks, GADM v4.1 and the GEE/ERA5 extracts. Names are compared after
# removing case, spaces and punctuation; ALIASES holds only spellings that
# occur in a source and differ from the canonical name (s03b checks both).
CANONICAL = [
    "Bagerhat", "Bandarban", "Barguna", "Barishal", "Bhola", "Bogura",
    "Brahmanbaria", "Chandpur", "Chapai Nawabganj", "Chattogram", "Chuadanga",
    "Cox's Bazar", "Cumilla", "Dhaka", "Dinajpur", "Faridpur", "Feni",
    "Gaibandha", "Gazipur", "Gopalganj", "Habiganj", "Jamalpur", "Jashore",
    "Jhalokati", "Jhenaidah", "Joypurhat", "Khagrachhari", "Khulna",
    "Kishoreganj", "Kurigram", "Kushtia", "Lakshmipur", "Lalmonirhat",
    "Madaripur", "Magura", "Manikganj", "Meherpur", "Moulvibazar",
    "Munshiganj", "Mymensingh", "Naogaon", "Narail", "Narayanganj",
    "Narsingdi", "Natore", "Netrokona", "Nilphamari", "Noakhali", "Pabna",
    "Panchagarh", "Patuakhali", "Pirojpur", "Rajbari", "Rajshahi",
    "Rangamati", "Rangpur", "Satkhira", "Shariatpur", "Sherpur", "Sirajganj",
    "Sunamganj", "Sylhet", "Tangail", "Thakurgaon",
]

ALIASES = {
    "barisal": "Barishal", "bogra": "Bogura", "brahamanbaria": "Brahmanbaria",
    "chapainawabgonj": "Chapai Nawabganj", "chapinawabgonj": "Chapai Nawabganj",
    "nawabganj": "Chapai Nawabganj", "nawabgonj": "Chapai Nawabganj",
    "chattagram": "Chattogram", "chittagong": "Chattogram", "coxbazar": "Cox's Bazar",
    "comilla": "Cumilla", "gopalgonj": "Gopalganj", "habigonj": "Habiganj",
    "hobigonj": "Habiganj", "jessore": "Jashore", "jhalakathi": "Jhalokati",
    "jhallokati": "Jhalokati", "khagrachari": "Khagrachhari", "kishoregonj": "Kishoreganj",
    "kustia": "Kushtia", "laksmipur": "Lakshmipur", "manikgonj": "Manikganj",
    "maulavibazar": "Moulvibazar", "maulovibazar": "Moulvibazar", "maulvibazar": "Moulvibazar",
    "munsigonj": "Munshiganj", "mymenshing": "Mymensingh", "noagaon": "Naogaon",
    "narayangonj": "Narayanganj", "netrakona": "Netrokona", "panchagar": "Panchagarh",
    "perojpur": "Pirojpur", "sirajgonj": "Sirajganj", "sunamgonj": "Sunamganj",
}

_CANON_KEY = {re.sub(r"[^a-z]", "", c.lower()): c for c in CANONICAL}


def panel_sha256(db=None):
    """SHA-256 of the Gold panel (rows ordered by district_id, harvest_year),
    used to tie test results to the data they were produced from."""
    import hashlib
    import duckdb
    con = duckdb.connect(str(db or V2_GOLD), read_only=True)
    df = con.execute("SELECT * FROM fact_boro_panel ORDER BY district_id, harvest_year").df()
    con.close()
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


class DataContractError(Exception):
    """An input or output violates the data contract in schema.py.  The
    message starts with a check ID ([SCHEMA], [DISTRICT], [KEY], [RANGE])
    and names the file, column and records involved."""


def canon_district(name: str):
    """Return the canonical district name, or None if not a district."""
    if name is None:
        return None
    key = re.sub(r"[^a-z]", "", str(name).lower())
    if not key:
        return None
    if key in _CANON_KEY:
        return _CANON_KEY[key]
    return ALIASES.get(key)
