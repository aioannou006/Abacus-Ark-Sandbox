"""Offline fixture mode: a FakeFetcher serving canned pages, so the whole
pipeline (steps 1-6) can run end-to-end with no network access.

Fixture school coverage, one per classification path:
  100001 Riverside      — Ofsted exact-postcode match + website evidence
  100002 St Hilda's     — website evidence only (exemption-likely path)
  100003 Oakfield       — Ofsted name match only, site has no signals
  100004 Greenway       — NO_EVIDENCE + no Ofsted  -> probable gap
  100005 Hillcrest      — breakfast club only      -> partial provision
  100006 Marsh Lane     — website unreachable      -> manual check
  100007 Fernbank       — no website in GIAS       -> manual check
  100008 Silver Birch   — probable gap upgraded by FIS hit
  100013 Cedar House    — JS-only site + Ofsted fuzzy-address match
  100014 Kingfisher     — provider-brand mention (Fit For Sport)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.http_client import FetchResult  # noqa: E402

_GENERIC_BODY = (
    "<p>Welcome to our school. We are proud of our pupils and our values of "
    "kindness, curiosity and respect. Term dates, newsletters, admissions "
    "information, curriculum overviews and policies are available from the "
    "school office. Our governors meet each term and our PTA organises "
    "events throughout the year.</p>"
)

PAGES = {
    "school1.example.sch.uk": (
        "<html><body><nav><a href='/clubs'>Clubs</a>"
        "<a href='/about'>About us</a></nav>" + _GENERIC_BODY + "</body></html>"
    ),
    "school1.example.sch.uk/clubs": (
        "<html><body><h1>Clubs</h1><p>Our after school club runs from "
        "3.15pm to 6.00pm every day in the main hall. Book via the "
        "office.</p></body></html>"
    ),
    "school2.example.sch.uk": (
        "<html><body>" + _GENERIC_BODY +
        "<p>We offer wraparound care from 8am to 6pm for all pupils, "
        "run by school staff.</p></body></html>"
    ),
    "school3.example.sch.uk": (
        "<html><body><a href='/parents'>Parents</a>" + _GENERIC_BODY +
        "</body></html>"
    ),
    "school3.example.sch.uk/parents": (
        "<html><body><p>Parent information: uniform, term dates, school "
        "dinners and attendance policies.</p></body></html>"
    ),
    "school4.example.sch.uk": (
        "<html><body><a href='/parents'>Parents</a>" + _GENERIC_BODY +
        "</body></html>"
    ),
    "school4.example.sch.uk/parents": (
        "<html><body><p>Newsletters and uniform information for "
        "families.</p></body></html>"
    ),
    "school5.example.sch.uk": (
        "<html><body>" + _GENERIC_BODY +
        "<p>Our breakfast club opens at 7.45am each morning, £2 per "
        "session.</p></body></html>"
    ),
    "school8.example.sch.uk": (
        "<html><body>" + _GENERIC_BODY + "</body></html>"
    ),
    "school13.example.sch.uk": (
        "<html><body><div id='app'></div></body></html>"  # JS-only shell
    ),
    "school14.example.sch.uk": (
        "<html><body>" + _GENERIC_BODY +
        "<p>Our partner Fit For Sport runs daily activity sessions on "
        "site until 6pm.</p></body></html>"
    ),
}

PREFIX_PAGES = {
    "fis.example/lambeth": (
        "<html><body><h1>Search results</h1><p>Silver Birch After School "
        "Club at St Agnes Hall — open 3pm to 6pm term time, ages "
        "4-11.</p></body></html>"
    ),
    "fis.example/richmond": "<html><body>No results found.</body></html>",
    "fis.example/kingston": "<html><body>No results found.</body></html>",
    "fis.example/wandsworth": "<html><body>No results found.</body></html>",
    "fis.example/merton": "<html><body>No results found.</body></html>",
}

ERROR_PREFIXES = ("school6.example.sch.uk",)


def fixture_config(cfg: dict) -> dict:
    cfg = dict(cfg)
    cfg["fis_search_templates"] = {
        "Wandsworth": "https://fis.example/wandsworth?q={query}",
        "Merton": "https://fis.example/merton?q={query}",
        "Lambeth": "https://fis.example/lambeth?q={query}",
        "Richmond upon Thames": "https://fis.example/richmond?q={query}",
        "Kingston upon Thames": "https://fis.example/kingston?q={query}",
    }
    return cfg


class FakeFetcher:
    """URL-keyed stand-in for PoliteFetcher (scheme-insensitive)."""

    def get(self, url: str, binary: bool = False,
            check_robots: bool = True) -> FetchResult:
        key = url.split("://", 1)[-1].rstrip("/")
        for prefix in ERROR_PREFIXES:
            if key.startswith(prefix):
                return FetchResult(url, None,
                                   error="connection refused (fixture)")
        if key in PAGES:
            return FetchResult(url, 200, text=PAGES[key])
        for prefix, html in PREFIX_PAGES.items():
            if key.startswith(prefix):
                return FetchResult(url, 200, text=html)
        return FetchResult(url, 404, text="not found")
