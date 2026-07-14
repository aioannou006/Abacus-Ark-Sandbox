"""Shared helpers: normalisation, CSV IO, logging."""

import csv
import logging
import re
import unicodedata
from pathlib import Path

log = logging.getLogger("wraparound")

# Words that carry no identity when comparing school / provider names.
NAME_STOPWORDS = {
    "the", "school", "primary", "junior", "infant", "infants", "juniors",
    "nursery", "academy", "college", "ce", "c", "of", "e", "cofe", "rc",
    "catholic", "church", "england", "voluntary", "aided", "controlled",
    "community", "foundation", "prep", "preparatory", "and", "st", "saint",
    "first", "at", "club", "ltd", "limited",
}


def setup_logging(logfile: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if logfile is not None:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(logfile, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def norm_text(s: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_postcode(s: str) -> str:
    """'sw18 2Pq ' -> 'SW182PQ'. Empty-safe."""
    return re.sub(r"\s+", "", (s or "").upper())


def postcode_district(s: str) -> str:
    """Outward code: 'SW18 2PQ' -> 'SW18'. Empty string if unparseable."""
    pc = norm_postcode(s)
    if len(pc) < 5:
        return ""
    return pc[:-3]


_STREET_ABBREV = {
    "rd": "road", "st": "street", "ave": "avenue", "av": "avenue",
    "ln": "lane", "cl": "close", "cres": "crescent", "gdns": "gardens",
    "sq": "square", "pl": "place", "dr": "drive", "ter": "terrace",
}


def norm_street(s: str) -> str:
    """Normalise a street line for fuzzy address comparison."""
    words = norm_text(s).split()
    return " ".join(_STREET_ABBREV.get(w, w) for w in words)


def name_tokens(s: str) -> set[str]:
    """Distinctive tokens of a school/provider name (stopwords removed)."""
    return {t for t in norm_text(s).split() if t not in NAME_STOPWORDS}


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log.info("wrote %s (%d rows)", path, len(rows))


def read_csv(path: Path, encoding: str = "utf-8") -> list[dict]:
    with open(path, newline="", encoding=encoding, errors="replace") as f:
        return list(csv.DictReader(f))


def resolve_column(fieldnames: list[str], *candidates: str) -> str | None:
    """Find a column by exact then substring match (case-insensitive).

    Source files (GIAS, Ofsted MI) rename headers between releases; this
    keeps the pipeline tolerant of cosmetic changes.
    """
    lowered = {f.lower().strip(): f for f in fieldnames}
    for cand in candidates:
        if cand.lower() in lowered:
            return lowered[cand.lower()]
    for cand in candidates:
        for low, orig in lowered.items():
            if cand.lower() in low:
                return orig
    return None
