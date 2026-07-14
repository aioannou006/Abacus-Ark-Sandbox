"""Step 6 — markdown summary report."""

import json
from pathlib import Path

from .util import log


def _by_borough(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r["borough"]] = out.get(r["borough"], 0) + 1
    return out


def write_report(cfg: dict, buckets: dict[str, list[dict]],
                 universe: list[dict], sources: dict, out_dir: Path) -> Path:
    confirmed, gaps, manual = (buckets["confirmed"], buckets["gaps"],
                               buckets["manual"])
    boroughs = sorted(cfg["boroughs"].values())
    probable = [g for g in gaps if g["classification"] == "PROBABLE_GAP"]
    partial = [g for g in gaps if g["classification"] == "PARTIAL_PROVISION"]

    lines = [
        "# SW London primary schools — wraparound provision gaps",
        "",
        f"Run date: {sources.get('run_date', 'unknown')}",
        "",
        "## Sources",
        "",
    ]
    for name, meta in sources.get("files", {}).items():
        lines.append(f"- **{name}**: {meta}")
    lines += [
        "",
        "## Universe",
        "",
        f"- Schools in scope: **{len(universe)}** across "
        f"{len(boroughs)} boroughs ({', '.join(boroughs)})",
        "",
        "## Classification counts by borough",
        "",
        "| Borough | Universe | Confirmed provision | Probable gap | "
        "Partial (breakfast only) | Manual check |",
        "|---|---|---|---|---|---|",
    ]
    uni_b, con_b = _by_borough(universe), _by_borough(confirmed)
    pro_b, par_b, man_b = (_by_borough(probable), _by_borough(partial),
                           _by_borough(manual))
    for b in boroughs:
        lines.append(
            f"| {b} | {uni_b.get(b, 0)} | {con_b.get(b, 0)} | "
            f"{pro_b.get(b, 0)} | {par_b.get(b, 0)} | {man_b.get(b, 0)} |"
        )
    lines.append(
        f"| **Total** | {len(universe)} | {len(confirmed)} | "
        f"{len(probable)} | {len(partial)} | {len(manual)} |"
    )

    def school_list(rows: list[dict]) -> list[str]:
        if not rows:
            return ["*(none)*"]
        return [f"- {r['name']} ({r['borough']}, {r['postcode']}, "
                f"URN {r['urn']})" for r in rows]

    lines += ["", "## Probable gaps (no after-school evidence found)", ""]
    lines += school_list(probable)
    lines += ["", "## Partial provision (breakfast only)", ""]
    lines += school_list(partial)
    lines += ["", "## Needs manual verification", ""]
    lines += school_list(manual)
    lines += [
        "",
        "## How to read this list",
        "",
        "**A probable gap is a candidate for phone verification, not a "
        "conclusion.** The pipeline distinguishes \"confirmed no club\" "
        "(which it can never establish) from \"no evidence found\" (which "
        "is what these lists contain).",
        "",
        "## Known limitations",
        "",
        "- Schools caring exclusively for their own pupils aged 3+ are "
        "usually exempt from separate Ofsted registration, so absence from "
        "the register is only a weak signal.",
        "- School websites go stale; a club may exist that the site does "
        "not mention, or a mentioned club may have closed.",
        "- Off-site clubs serving several schools (e.g. one hall covering a "
        "cluster) will not match on postcode or address and may be missed.",
        "- JS-only websites cannot be read by this sweep and land in the "
        "manual-check list.",
        "- FIS directories are incomplete and their search endpoints "
        "change; a failed FIS check leaves the school on the shortlist.",
        "",
        "**Next step:** phone-verify every school in `probable_gaps.csv` "
        "before building any outreach on it.",
    ]

    path = out_dir / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "sources.json").write_text(
        json.dumps(sources, indent=2), encoding="utf-8")
    log.info("wrote %s", path)
    return path
