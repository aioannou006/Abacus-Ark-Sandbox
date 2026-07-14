# SW London schools without after-school provision

A re-runnable pipeline that produces a **scored candidate list** of primary
schools in south west London with no identifiable after-school (wraparound)
provision. The output is a shortlist for manual verification, **not a final
answer**: the pipeline distinguishes "no evidence found" from "confirmed no
club" and never conflates the two — the latter can only be established by a
phone call.

## Scope

Wandsworth (212), Merton (315), Lambeth (208), Richmond upon Thames (318),
Kingston upon Thames (314). Open, state-funded **and** independent schools
with a primary age range (statutory low age ≤ 5, high age ≥ 7). The borough
list, age thresholds and every other tunable live in
[`pipeline/config.py`](pipeline/config.py) — widen scope by adding LA codes
there.

## Data governance

Public datasets and public websites only. No personal data enters the
pipeline; all outputs are school-level aggregates and flags.

## Running

```bash
pip install -r requirements.txt
python3 run_pipeline.py                    # full live run
python3 run_pipeline.py --fixtures         # offline end-to-end demo
python3 -m unittest discover tests         # test suite
```

Each run writes to `outputs/run_<date>/`:

| File | Contents |
|---|---|
| `schools_universe.csv` | Step 1 — all in-scope schools (sanity check: 250–400 expected; aborts outside that range unless `--force`) |
| `ofsted_matches.csv` | Step 2 — register match per school (`exact`/`fuzzy`/`name`/`none`) |
| `website_evidence.csv` | Step 3 — per-school classification with matched phrase + source URL |
| `confirmed_provision.csv` | Step 4/5 — schools with evidence of a club (excluded from outreach) |
| `probable_gaps.csv` | **Deliverable** — `PROBABLE_GAP` and `PARTIAL_PROVISION` (breakfast-only) schools, FIS-cross-checked |
| `manual_check.csv` | **Deliverable** — unverifiable sites needing a human look |
| `summary.md`, `sources.json`, `run.log` | Step 6 — report, source publication dates, full log |

### Network requirements

A live run needs outbound HTTPS to:

- `ea-edubase-api-prod.azurewebsites.net` (GIAS daily extract)
- `www.gov.uk` + `assets.publishing.service.gov.uk` (Ofsted childcare dataset)
- the ~300 school websites in the GIAS extract (arbitrary hosts)
- the borough FIS directories (see `fis_search_templates` in config)

The sweep is polite by design: global ~1.3 req/s ceiling, honest
user agent, robots.txt respected, one retry, failures logged and surfaced
as `UNVERIFIABLE` rather than retried aggressively.

## Classification model

Step 3 classifies each school's website: `CONFIRMED_CLUB` (after-school
signal term or known provider brand found — matched phrase and URL are
recorded for audit), `BREAKFAST_ONLY`, `NO_EVIDENCE` (site read fine,
nothing found), `UNVERIFIABLE` (no site / dead site / JS-only). Step 4
combines this with the Ofsted register match:

| Ofsted match | Website | Outcome |
|---|---|---|
| any | CONFIRMED_CLUB | confirmed provision |
| none | CONFIRMED_CLUB | confirmed (school-run club likely exempt from registration) |
| any | other | confirmed (site may be poor/stale) |
| none | NO_EVIDENCE | **probable gap** |
| none | BREAKFAST_ONLY | **partial provision** |
| none | UNVERIFIABLE | manual check |

**Registration exemption caveat:** schools caring only for their own pupils
aged 3+ generally don't need separate Ofsted registration, so
`ofsted_match = none` is a weak signal on its own — that's why website
evidence dominates the score.

Step 5 re-checks the shortlist against each borough's Family Information
Service directory and upgrades any hits to confirmed provision with the FIS
URL as source.

## Verification loop

After a full run:

```bash
python3 verify_sample.py outputs/run_<date> --seed 1   # sample 10 + 10
# ...manually verify each row, fill in manual_verdict...
python3 verify_sample.py outputs/run_<date> --evaluate
```

More than 2 misclassified in either sample → revise `afterschool_signal_terms`
/ matching logic in config and re-run. Maximum three iterations; if still
failing, escalate with a written account of the failure mode rather than
shipping the list.

## Re-runnability

All source URLs, borough codes, signal terms and provider brands sit in the
single `CONFIG` block. Runs are dated, source publication dates are logged
to `sources.json`, and nothing is hard-coded to a one-off date. This list
dates quickly (wraparound entitlement pressure from September 2026) —
re-run rather than reuse.

An example fixture-run output is committed under
[`examples/`](examples/) so the output shape is visible without running
anything.
