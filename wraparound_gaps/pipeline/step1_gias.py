"""Step 1 — build the school universe from the GIAS full extract."""

import datetime as dt
from pathlib import Path

from .util import log, read_csv, resolve_column, write_csv

UNIVERSE_FIELDS = [
    "urn", "name", "la_code", "borough", "type", "phase",
    "low_age", "high_age", "status", "street", "postcode",
    "website", "phone", "nursery_provision",
]


def download_gias(cfg: dict, fetcher, cache_dir: Path,
                  today: dt.date) -> tuple[Path, str]:
    """Fetch the newest available daily extract; return (path, source_date)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    for delta in range(cfg["gias_lookback_days"] + 1):
        day = today - dt.timedelta(days=delta)
        stamp = day.strftime("%Y%m%d")
        url = cfg["gias_daily_url_template"].format(yyyymmdd=stamp)
        dest = cache_dir / f"edubasealldata{stamp}.csv"
        if dest.exists():
            log.info("GIAS extract already cached: %s", dest)
            return dest, day.isoformat()
        log.info("trying GIAS extract %s", url)
        result = fetcher.get(url, binary=True)
        if result.ok and result.content:
            dest.write_bytes(result.content)
            log.info("downloaded GIAS extract for %s (%d bytes)",
                     day.isoformat(), len(result.content))
            return dest, day.isoformat()
        log.info("no extract for %s (%s)", day.isoformat(),
                 result.error or f"HTTP {result.status}")
    raise RuntimeError(
        f"No GIAS extract found in the last {cfg['gias_lookback_days']} days; "
        "check gias_daily_url_template or download manually from "
        "https://get-information-schools.service.gov.uk/Downloads"
    )


def _to_int(s: str) -> int | None:
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def build_universe(cfg: dict, gias_csv: Path, out_path: Path,
                   force: bool = False) -> list[dict]:
    rows = read_csv(gias_csv, encoding=cfg["gias_encoding"])
    if not rows:
        raise RuntimeError(f"GIAS file {gias_csv} is empty")

    fields = list(rows[0].keys())
    col = {
        "urn": resolve_column(fields, "URN"),
        "name": resolve_column(fields, "EstablishmentName"),
        "la_code": resolve_column(fields, "LA (code)", "LA code"),
        "type": resolve_column(fields, "TypeOfEstablishment (name)",
                               "TypeOfEstablishment"),
        "phase": resolve_column(fields, "PhaseOfEducation (name)",
                                "PhaseOfEducation"),
        "low": resolve_column(fields, "StatutoryLowAge"),
        "high": resolve_column(fields, "StatutoryHighAge"),
        "status": resolve_column(fields, "EstablishmentStatus (name)",
                                 "EstablishmentStatus"),
        "street": resolve_column(fields, "Street"),
        "postcode": resolve_column(fields, "Postcode"),
        "website": resolve_column(fields, "SchoolWebsite"),
        "phone": resolve_column(fields, "TelephoneNum"),
        "nursery": resolve_column(fields, "NurseryProvision (name)",
                                  "NurseryProvision"),
    }
    missing = [k for k, v in col.items() if v is None]
    if missing:
        raise RuntimeError(f"GIAS columns not found: {missing} in {gias_csv}")

    boroughs = cfg["boroughs"]
    seen_urns: set[str] = set()
    universe: list[dict] = []
    for r in rows:
        la = (r[col["la_code"]] or "").strip()
        if la not in boroughs:
            continue
        if (r[col["status"]] or "").strip() not in cfg["open_statuses"]:
            continue
        phase = (r[col["phase"]] or "").strip()
        if phase in cfg["excluded_phases"]:
            continue
        if (r[col["type"]] or "").strip() in cfg["excluded_types"]:
            continue
        low, high = _to_int(r[col["low"]]), _to_int(r[col["high"]])
        # Primary phase by statutory age range: admits infants (<=5) and
        # keeps them past key stage 1 entry (>=7). Excludes nursery-only
        # (high < 7) and secondary-only (low > 5) automatically.
        if low is None or high is None:
            continue
        if low > cfg["statutory_low_age_max"] or high < cfg["statutory_high_age_min"]:
            continue
        urn = (r[col["urn"]] or "").strip()
        if not urn or urn in seen_urns:
            continue
        seen_urns.add(urn)
        universe.append({
            "urn": urn,
            "name": (r[col["name"]] or "").strip(),
            "la_code": la,
            "borough": boroughs[la],
            "type": (r[col["type"]] or "").strip(),
            "phase": phase,
            "low_age": low,
            "high_age": high,
            "status": (r[col["status"]] or "").strip(),
            "street": (r[col["street"]] or "").strip(),
            "postcode": (r[col["postcode"]] or "").strip(),
            "website": (r[col["website"]] or "").strip(),
            "phone": (r[col["phone"]] or "").strip(),
            "nursery_provision": (r[col["nursery"]] or "").strip(),
        })

    n = len(universe)
    lo, hi = cfg["universe_sanity_min"], cfg["universe_sanity_max"]
    log.info("universe: %d schools in scope (sanity range %d-%d)", n, lo, hi)
    if not lo <= n <= hi and not force:
        raise RuntimeError(
            f"Universe size {n} outside sanity range {lo}-{hi}. "
            "This usually means a filter or source-format regression. "
            "Inspect the GIAS file, then re-run with --force to proceed."
        )
    write_csv(out_path, universe, UNIVERSE_FIELDS)
    return universe
