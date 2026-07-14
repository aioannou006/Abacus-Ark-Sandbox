"""Single configuration block for the SW London wraparound-gaps pipeline.

Everything that should change between runs or when scope widens lives here:
source URLs, borough codes, age thresholds, signal terms, provider brands,
crawl politeness settings, and FIS directory endpoints. No other module
hard-codes any of these.
"""

CONFIG = {
    # ------------------------------------------------------------------
    # Geography. GIAS "LA (code)" values. Add boroughs here to widen scope.
    # ------------------------------------------------------------------
    "boroughs": {
        "212": "Wandsworth",
        "315": "Merton",
        "208": "Lambeth",
        "318": "Richmond upon Thames",
        "314": "Kingston upon Thames",
    },

    # ------------------------------------------------------------------
    # School universe filters (Step 1)
    # ------------------------------------------------------------------
    # Primary phase is defined by statutory age range, not the Phase field,
    # so independents (Phase = "Not applicable") are included correctly.
    "statutory_low_age_max": 5,   # school must admit at age <= 5
    "statutory_high_age_min": 7,  # ...and keep pupils to at least age 7
    "open_statuses": ["Open", "Open, but proposed to close"],
    # Phases that can never be in-scope even if ages look primary-ish.
    "excluded_phases": ["Nursery", "16 plus"],
    # Establishment types that are not schools at all.
    "excluded_types": [
        "Children's centre",
        "Children's centre linked site",
        "Online provider",
    ],
    # Expected universe size; a result outside this range aborts the run
    # (override with --force) because it usually means a filter regression
    # or a malformed source file.
    "universe_sanity_min": 250,
    "universe_sanity_max": 400,

    # ------------------------------------------------------------------
    # GIAS source (Step 1)
    # ------------------------------------------------------------------
    # DfE publishes a full extract daily at a date-stamped URL
    # (linked from https://get-information-schools.service.gov.uk/Downloads).
    "gias_daily_url_template": (
        "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/"
        "public/edubasealldata{yyyymmdd}.csv"
    ),
    "gias_lookback_days": 7,      # walk back if today's file isn't up yet
    "gias_encoding": "cp1252",

    # ------------------------------------------------------------------
    # Ofsted childcare register source (Step 2)
    # ------------------------------------------------------------------
    # Monthly-ish management information publication. The pipeline scrapes
    # this page for the newest childcare-providers data file. If the page
    # layout changes, pin the direct file URL in `ofsted_data_url`.
    "ofsted_dataset_page": (
        "https://www.gov.uk/government/statistical-data-sets/"
        "childcare-providers-and-inspections-management-information"
    ),
    "ofsted_data_url": None,      # optional direct-link override
    # Keep only non-domestic (i.e. not childminder-at-home) registrations;
    # school-site out-of-school clubs register as this type.
    "ofsted_provider_type_keywords": ["non-domestic"],

    # ------------------------------------------------------------------
    # Website evidence sweep (Step 3)
    # ------------------------------------------------------------------
    # Terms that count as after-school / wraparound care evidence.
    "afterschool_signal_terms": [
        "after school club",
        "after-school club",
        "afterschool club",
        "after school care",
        "after-school care",
        "after school provision",
        "wraparound",
        "wrap around care",
        "wrap-around care",
        "extended day",
        "extended schools",
        "extended school provision",
        "out of school club",
        "out-of-school club",
    ],
    # Terms that count only as breakfast provision.
    "breakfast_signal_terms": [
        "breakfast club",
        "breakfast provision",
        "before school club",
        "before-school club",
    ],
    # Known wraparound provider brands; a brand mention counts as
    # after-school evidence.
    "provider_brands": [
        "fit for sport",
        "premier education",
        "junior adventures group",
        "kids city",
        "kidscity",
        "scl education",
        "energy kidz",
    ],
    # URL paths tried directly on each site (in addition to links found on
    # the homepage whose text/href matches `link_keywords`).
    "candidate_paths": [
        "wraparound",
        "wraparound-care",
        "after-school-club",
        "clubs",
        "breakfast-club",
        "extended-schools",
        "childcare",
        "parents",
    ],
    # A homepage link is followed when its href or anchor text contains any
    # of these.
    "link_keywords": [
        "wraparound",
        "after-school",
        "after school",
        "clubs",
        "club",
        "breakfast",
        "extended",
        "childcare",
        "parents",
    ],
    "max_pages_per_site": 8,      # homepage + up to 7 candidate pages
    # A fetched homepage with less visible text than this is treated as
    # JS-rendered and the school goes to UNVERIFIABLE.
    "min_visible_text_chars": 200,

    # ------------------------------------------------------------------
    # HTTP politeness (Steps 2, 3, 5)
    # ------------------------------------------------------------------
    "user_agent": (
        "AbacusArk-wraparound-research/1.0 "
        "(childcare provision mapping; contact: anthony@abacusark.com)"
    ),
    "request_min_interval_s": 0.75,   # ~1.3 req/s ceiling, global
    "request_timeout_s": 20,
    "request_retries": 1,             # one retry on transient failure
    "respect_robots_txt": True,

    # ------------------------------------------------------------------
    # Borough Family Information Service directories (Step 5)
    # ------------------------------------------------------------------
    # {query} is the URL-encoded school name. These are best-effort search
    # endpoints; a failed or unparseable response marks the school
    # fis_checked=error and leaves it on the shortlist.
    "fis_search_templates": {
        "Wandsworth": (
            "https://fis.wandsworth.gov.uk/kb5/wandsworth/fsd/"
            "results.page?qt={query}"
        ),
        "Merton": (
            "https://directories.merton.gov.uk/kb5/merton/directory/"
            "results.action?qt={query}"
        ),
        "Lambeth": (
            "https://www.lambeth.gov.uk/family-information-directory"
            "?search_api_fulltext={query}"
        ),
        "Richmond upon Thames": (
            "https://kr.afcinfo.org.uk/childcare_providers"
            "?search_childcare_provider%5Bterm%5D={query}"
        ),
        "Kingston upon Thames": (
            "https://kr.afcinfo.org.uk/childcare_providers"
            "?search_childcare_provider%5Bterm%5D={query}"
        ),
    },
    # A FIS results page counts as a hit only if it mentions the school name
    # AND one of these terms nearby (whole-page match is enough for kb5
    # sites, whose result snippets are short).
    "fis_hit_terms": [
        "after school",
        "after-school",
        "out of school",
        "wraparound",
        "playscheme",
    ],

    # ------------------------------------------------------------------
    # Verification loop (post-run)
    # ------------------------------------------------------------------
    "verify_sample_size": 10,     # per class (CONFIRMED_CLUB, NO_EVIDENCE)
    "verify_max_misclassified": 2,
    "verify_max_iterations": 3,
}
