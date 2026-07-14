"""Step 5 — Family Information Service cross-check (shortlist only).

Best-effort: each borough directory is a different platform, and their
markup changes. A hit (school name + out-of-school term on the results
page) downgrades the school to confirmed provision with the FIS URL as
source. A failed or blocked request marks fis_checked=error and leaves
the school on the shortlist — never silently.
"""

from pathlib import Path
from urllib.parse import quote_plus

from .step4_scoring import OUTPUT_FIELDS
from .util import log, name_tokens, norm_text, write_csv

FIS_FIELDS = OUTPUT_FIELDS + ["fis_checked", "fis_url"]


def check_school(school: dict, cfg: dict, fetcher) -> tuple[str, str]:
    """Return (fis_checked, fis_url): hit / no_hit / error / no_directory."""
    template = cfg["fis_search_templates"].get(school["borough"])
    if not template:
        return "no_directory", ""
    url = template.format(query=quote_plus(school["name"]))
    resp = fetcher.get(url)
    if not resp.ok:
        log.warning("FIS check failed for %s (%s): %s",
                    school["name"], school["borough"],
                    resp.error or resp.status)
        return "error", url
    page = norm_text(resp.text)
    tokens = name_tokens(school["name"])
    school_mentioned = tokens and all(t in page for t in tokens)
    provision_term = any(norm_text(t) in page for t in cfg["fis_hit_terms"])
    if school_mentioned and provision_term:
        return "hit", resp.url
    return "no_hit", url


def cross_check(buckets: dict[str, list[dict]], cfg: dict, fetcher,
                out_dir: Path) -> dict[str, list[dict]]:
    """Re-write probable_gaps.csv and confirmed_provision.csv after FIS."""
    still_gaps, upgraded = [], []
    for school in buckets["gaps"]:
        checked, url = check_school(school, cfg, fetcher)
        school = {**school, "fis_checked": checked, "fis_url": url}
        if checked == "hit":
            school["classification"] = "CONFIRMED_PROVISION"
            school["rationale"] = (
                "FIS directory lists out-of-school provision matching this "
                f"school (source: {url}). Previously: {school['rationale']}"
            )
            upgraded.append(school)
        else:
            still_gaps.append(school)

    if upgraded:
        log.info("FIS cross-check upgraded %d schools to confirmed", len(upgraded))
    confirmed = [
        {**s, "fis_checked": s.get("fis_checked", ""), "fis_url": s.get("fis_url", "")}
        for s in buckets["confirmed"]
    ] + upgraded
    manual = [
        {**s, "fis_checked": "", "fis_url": ""} for s in buckets["manual"]
    ]

    write_csv(out_dir / "confirmed_provision.csv", confirmed, FIS_FIELDS)
    write_csv(out_dir / "probable_gaps.csv", still_gaps, FIS_FIELDS)
    write_csv(out_dir / "manual_check.csv", manual, FIS_FIELDS)
    return {"confirmed": confirmed, "gaps": still_gaps, "manual": manual}
