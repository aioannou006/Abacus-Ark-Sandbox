"""Step 4 — combine Ofsted + website evidence into the three output lists.

Scoring matrix (from the brief):

  Ofsted match | Website class   | Outcome
  -------------+-----------------+------------------------------------------
  any match    | CONFIRMED_CLUB  | confirmed provision
  none         | CONFIRMED_CLUB  | confirmed provision (registration
               |                 | exemption likely — school-run club)
  any match    | anything else   | confirmed provision (site may be poor
               |                 | or club runs under a provider brand)
  none         | NO_EVIDENCE     | shortlist: PROBABLE GAP
  none         | BREAKFAST_ONLY  | shortlist: PARTIAL PROVISION
  none         | UNVERIFIABLE    | manual-check list
"""

from pathlib import Path

from .step3_websweep import (CLASS_BREAKFAST, CLASS_CONFIRMED,
                             CLASS_NO_EVIDENCE, CLASS_UNVERIFIABLE)
from .util import log, write_csv

OUTPUT_FIELDS = [
    "urn", "name", "borough", "postcode", "phone", "website",
    "classification", "rationale",
    "ofsted_match", "ofsted_provider", "ofsted_registration",
    "website_class", "evidence_term", "evidence_url", "evidence_context",
    "fetch_note",
]


def score(schools: list[dict], ofsted: dict[str, dict],
          sweep: dict[str, dict], out_dir: Path) -> dict[str, list[dict]]:
    confirmed, gaps, manual = [], [], []
    for s in schools:
        o = ofsted.get(s["urn"], {})
        w = sweep.get(s["urn"], {})
        ofsted_match = o.get("ofsted_match", "none")
        web_class = w.get("website_class", CLASS_UNVERIFIABLE)
        has_ofsted = ofsted_match != "none"

        if has_ofsted and web_class == CLASS_CONFIRMED:
            cls, rationale, bucket = (
                "CONFIRMED_PROVISION",
                "Ofsted-registered provider at address AND after-school "
                "evidence on school website.",
                confirmed,
            )
        elif web_class == CLASS_CONFIRMED:
            cls, rationale, bucket = (
                "CONFIRMED_PROVISION",
                "After-school evidence on school website; no Ofsted register "
                "match (school-run club likely exempt from registration).",
                confirmed,
            )
        elif has_ofsted:
            cls, rationale, bucket = (
                "CONFIRMED_PROVISION",
                f"Ofsted-registered provider matched ({ofsted_match}) but no "
                "website evidence — site may be poor, stale, or the club "
                "advertised elsewhere.",
                confirmed,
            )
        elif web_class == CLASS_NO_EVIDENCE:
            cls, rationale, bucket = (
                "PROBABLE_GAP",
                "Website fetched successfully with no wraparound signals and "
                "no Ofsted register match. Requires phone confirmation "
                "before any outreach.",
                gaps,
            )
        elif web_class == CLASS_BREAKFAST:
            cls, rationale, bucket = (
                "PARTIAL_PROVISION",
                "Breakfast-club evidence only; no after-school evidence and "
                "no Ofsted register match. Requires phone confirmation.",
                gaps,
            )
        else:  # UNVERIFIABLE
            cls, rationale, bucket = (
                "MANUAL_CHECK",
                f"Website evidence unavailable "
                f"({w.get('fetch_note') or 'unverifiable'}) and no Ofsted "
                "register match — needs a manual check.",
                manual,
            )

        bucket.append({
            **{k: s.get(k, "") for k in
               ("urn", "name", "borough", "postcode", "phone", "website")},
            "classification": cls,
            "rationale": rationale,
            "ofsted_match": ofsted_match,
            "ofsted_provider": o.get("ofsted_provider", ""),
            "ofsted_registration": o.get("ofsted_registration", ""),
            "website_class": web_class,
            "evidence_term": w.get("evidence_term", ""),
            "evidence_url": w.get("evidence_url", ""),
            "evidence_context": w.get("evidence_context", ""),
            "fetch_note": w.get("fetch_note", ""),
        })

    write_csv(out_dir / "confirmed_provision.csv", confirmed, OUTPUT_FIELDS)
    write_csv(out_dir / "probable_gaps.csv", gaps, OUTPUT_FIELDS)
    write_csv(out_dir / "manual_check.csv", manual, OUTPUT_FIELDS)
    log.info("scoring: %d confirmed, %d shortlisted, %d manual-check",
             len(confirmed), len(gaps), len(manual))
    return {"confirmed": confirmed, "gaps": gaps, "manual": manual}
