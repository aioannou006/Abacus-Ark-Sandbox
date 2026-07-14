#!/usr/bin/env python3
"""Run the SW London wraparound-gaps pipeline.

Usage:
    python3 run_pipeline.py                 # full live run
    python3 run_pipeline.py --force         # ignore universe sanity check
    python3 run_pipeline.py --fixtures      # offline end-to-end demo run
    python3 run_pipeline.py --output-root outputs

Each run writes to a dated folder under --output-root and records source
publication dates in sources.json. Live runs need outbound HTTPS to
gov.uk, the GIAS Azure endpoint, and school/FIS websites.
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pipeline import (step1_gias, step2_ofsted, step3_websweep,  # noqa: E402
                      step4_scoring, step5_fis, step6_report)
from pipeline.config import CONFIG  # noqa: E402
from pipeline.util import log, postcode_district, setup_logging  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-root", default=str(HERE / "outputs"))
    p.add_argument("--force", action="store_true",
                   help="proceed even if the universe sanity check fails")
    p.add_argument("--fixtures", action="store_true",
                   help="offline demo run against tests/fixtures data")
    p.add_argument("--skip-websweep", action="store_true",
                   help="skip Step 3 (all schools become UNVERIFIABLE)")
    p.add_argument("--skip-fis", action="store_true",
                   help="skip Step 5 FIS cross-check")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    today = dt.date.today()
    run_name = f"run_{today.isoformat()}" + ("_fixture" if args.fixtures else "")
    out_dir = Path(args.output_root) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(out_dir / "run.log")
    cfg = dict(CONFIG)
    sources = {"run_date": today.isoformat(), "files": {}}

    if args.fixtures:
        from tests.fixture_support import FakeFetcher, fixture_config
        cfg = fixture_config(cfg)
        fetcher = FakeFetcher()
        gias_csv = HERE / "tests" / "fixtures" / "gias_sample.csv"
        ofsted_path = HERE / "tests" / "fixtures" / "ofsted_sample.csv"
        sources["files"]["GIAS"] = "fixture: tests/fixtures/gias_sample.csv"
        sources["files"]["Ofsted"] = "fixture: tests/fixtures/ofsted_sample.csv"
        args.force = True  # fixture universe is tiny by design
    else:
        from pipeline.http_client import PoliteFetcher
        fetcher = PoliteFetcher(cfg)
        cache = out_dir / "source_data"
        gias_csv, gias_date = step1_gias.download_gias(cfg, fetcher, cache, today)
        sources["files"]["GIAS"] = f"{gias_csv.name} (extract date {gias_date})"
        ofsted_path = step2_ofsted.download_ofsted(cfg, fetcher, cache)
        sources["files"]["Ofsted"] = ofsted_path.name

    # Step 1 — universe
    log.info("=== Step 1: build school universe ===")
    universe = step1_gias.build_universe(
        cfg, gias_csv, out_dir / "schools_universe.csv", force=args.force)

    # Step 2 — Ofsted register match
    log.info("=== Step 2: Ofsted register match ===")
    districts = {postcode_district(s["postcode"]) for s in universe} - {""}
    providers = step2_ofsted.filter_providers(
        cfg, step2_ofsted.load_ofsted_rows(ofsted_path), districts)
    ofsted_matches = step2_ofsted.match_schools(
        universe, providers, out_dir / "ofsted_matches.csv")

    # Step 3 — website sweep
    log.info("=== Step 3: website evidence sweep ===")
    if args.skip_websweep:
        sweep = {}
        log.info("skipped by --skip-websweep")
    else:
        sweep = step3_websweep.sweep_all(
            universe, cfg, fetcher, out_dir / "website_evidence.csv")

    # Step 4 — scoring
    log.info("=== Step 4: scoring and shortlist ===")
    buckets = step4_scoring.score(universe, ofsted_matches, sweep, out_dir)

    # Step 5 — FIS cross-check on the shortlist
    log.info("=== Step 5: FIS cross-check ===")
    if args.skip_fis:
        log.info("skipped by --skip-fis")
    else:
        buckets = step5_fis.cross_check(buckets, cfg, fetcher, out_dir)

    # Step 6 — summary report
    log.info("=== Step 6: summary report ===")
    step6_report.write_report(cfg, buckets, universe, sources, out_dir)

    log.info("done — outputs in %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
