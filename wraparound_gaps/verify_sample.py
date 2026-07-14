#!/usr/bin/env python3
"""Verification loop for a pipeline run (see brief: max 3 iterations).

1. Sample:   python3 verify_sample.py outputs/run_2026-XX-XX --seed 1
   Writes verification_sample.csv into the run folder: 10 random
   CONFIRMED_CLUB and 10 random NO_EVIDENCE schools, with a blank
   `manual_verdict` column. Check each school by hand (visit the site /
   phone) and fill in CORRECT or WRONG plus notes.

2. Evaluate: python3 verify_sample.py outputs/run_2026-XX-XX --evaluate
   Counts WRONG per class. More than 2 wrong in either sample fails the
   run: revise signal terms / matching logic in pipeline/config.py and
   re-run the pipeline. After 3 failed iterations, stop and escalate with
   a written account of the failure mode instead of shipping the list.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline.config import CONFIG  # noqa: E402

SAMPLE_COLS = ["urn", "name", "borough", "website", "phone", "website_class",
               "evidence_term", "evidence_url", "manual_verdict", "notes"]


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sample(run_dir: Path, seed: int) -> Path:
    rows = read_rows(run_dir / "website_evidence.csv")
    phones = {r["urn"]: r.get("phone", "")
              for r in read_rows(run_dir / "schools_universe.csv")}
    rng = random.Random(seed)
    n = CONFIG["verify_sample_size"]
    picked = []
    for cls in ("CONFIRMED_CLUB", "NO_EVIDENCE"):
        pool = [r for r in rows if r["website_class"] == cls]
        chosen = rng.sample(pool, min(n, len(pool)))
        if len(pool) < n:
            print(f"note: only {len(pool)} {cls} schools available")
        picked.extend(chosen)
    out = run_dir / "verification_sample.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_COLS, extrasaction="ignore")
        w.writeheader()
        for r in picked:
            w.writerow({**r, "phone": phones.get(r["urn"], ""),
                        "manual_verdict": "", "notes": ""})
    print(f"wrote {out} — fill manual_verdict with CORRECT or WRONG, "
          f"then run with --evaluate")
    return out


def evaluate(run_dir: Path) -> int:
    rows = read_rows(run_dir / "verification_sample.csv")
    unfilled = [r for r in rows if r["manual_verdict"].strip().upper()
                not in ("CORRECT", "WRONG")]
    if unfilled:
        print(f"{len(unfilled)} rows still need a CORRECT/WRONG verdict.")
        return 2
    limit = CONFIG["verify_max_misclassified"]
    failed = False
    for cls in ("CONFIRMED_CLUB", "NO_EVIDENCE"):
        wrong = sum(1 for r in rows if r["website_class"] == cls
                    and r["manual_verdict"].strip().upper() == "WRONG")
        total = sum(1 for r in rows if r["website_class"] == cls)
        status = "PASS" if wrong <= limit else "FAIL"
        print(f"{cls}: {wrong}/{total} misclassified — {status}")
        failed = failed or wrong > limit
    if failed:
        print(f"\nFAIL: revise signal terms / matching logic in "
              f"pipeline/config.py and re-run (max "
              f"{CONFIG['verify_max_iterations']} iterations, then escalate "
              "with a written failure account).")
        return 1
    print("\nPASS: classifications are within tolerance.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--seed", type=int, default=0,
                   help="sampling seed (vary per iteration)")
    p.add_argument("--evaluate", action="store_true")
    args = p.parse_args()
    if args.evaluate:
        return evaluate(args.run_dir)
    sample(args.run_dir, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
