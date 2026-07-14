# SW London primary schools — wraparound provision gaps

Run date: 2026-07-14

## Sources

- **GIAS**: fixture: tests/fixtures/gias_sample.csv
- **Ofsted**: fixture: tests/fixtures/ofsted_sample.csv

## Universe

- Schools in scope: **10** across 5 boroughs (Kingston upon Thames, Lambeth, Merton, Richmond upon Thames, Wandsworth)

## Classification counts by borough

| Borough | Universe | Confirmed provision | Probable gap | Partial (breakfast only) | Manual check |
|---|---|---|---|---|---|
| Kingston upon Thames | 2 | 1 | 0 | 1 | 0 |
| Lambeth | 2 | 2 | 0 | 0 | 0 |
| Merton | 2 | 1 | 0 | 0 | 1 |
| Richmond upon Thames | 2 | 1 | 1 | 0 | 0 |
| Wandsworth | 2 | 1 | 0 | 0 | 1 |
| **Total** | 10 | 6 | 1 | 1 | 2 |

## Probable gaps (no after-school evidence found)

- Greenway Primary School (Richmond upon Thames, TW9 1AA, URN 100004)

## Partial provision (breakfast only)

- Hillcrest Primary School (Kingston upon Thames, KT1 2BB, URN 100005)

## Needs manual verification

- Marsh Lane Primary School (Wandsworth, SW11 3CC, URN 100006)
- Fernbank Primary School (Merton, CR4 4DD, URN 100007)

## How to read this list

**A probable gap is a candidate for phone verification, not a conclusion.** The pipeline distinguishes "confirmed no club" (which it can never establish) from "no evidence found" (which is what these lists contain).

## Known limitations

- Schools caring exclusively for their own pupils aged 3+ are usually exempt from separate Ofsted registration, so absence from the register is only a weak signal.
- School websites go stale; a club may exist that the site does not mention, or a mentioned club may have closed.
- Off-site clubs serving several schools (e.g. one hall covering a cluster) will not match on postcode or address and may be missed.
- JS-only websites cannot be read by this sweep and land in the manual-check list.
- FIS directories are incomplete and their search endpoints change; a failed FIS check leaves the school on the shortlist.

**Next step:** phone-verify every school in `probable_gaps.csv` before building any outreach on it.