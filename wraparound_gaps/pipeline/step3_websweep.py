"""Step 3 — website evidence sweep.

For each school with a website: fetch the homepage, follow links whose
text/href look wraparound-related, try a short list of candidate paths,
and search the visible text for signal terms. Every classification that
asserts provision exists records the matched phrase and source URL so it
can be audited.
"""

from pathlib import Path
from urllib.parse import urljoin, urlparse

from .util import log, write_csv

CLASS_CONFIRMED = "CONFIRMED_CLUB"
CLASS_BREAKFAST = "BREAKFAST_ONLY"
CLASS_NO_EVIDENCE = "NO_EVIDENCE"
CLASS_UNVERIFIABLE = "UNVERIFIABLE"

SWEEP_FIELDS = [
    "urn", "name", "borough", "website", "website_class",
    "evidence_term", "evidence_url", "evidence_context",
    "pages_fetched", "fetch_note",
]


def normalise_site_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not raw.lower().startswith(("http://", "https://")):
        raw = "http://" + raw
    return raw


def visible_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split()).lower()


def candidate_links(html: str, base_url: str, cfg: dict) -> list[str]:
    """Same-host links whose href or anchor text matches a keyword."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc
    found: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(separator=" ").lower()
        blob = href.lower() + " " + text
        if not any(k in blob for k in cfg["link_keywords"]):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https") or parsed.netloc != host:
            continue
        absolute = absolute.split("#")[0]
        if absolute not in found:
            found.append(absolute)
    return found


def find_signals(text: str, cfg: dict) -> tuple[str, str, str]:
    """Return (kind, term, context): kind in afterschool|breakfast|''."""
    for term in cfg["afterschool_signal_terms"] + cfg["provider_brands"]:
        idx = text.find(term)
        if idx >= 0:
            ctx = text[max(0, idx - 60): idx + len(term) + 60]
            return "afterschool", term, ctx
    for term in cfg["breakfast_signal_terms"]:
        idx = text.find(term)
        if idx >= 0:
            ctx = text[max(0, idx - 60): idx + len(term) + 60]
            return "breakfast", term, ctx
    return "", "", ""


def sweep_school(school: dict, cfg: dict, fetcher) -> dict:
    base = {
        "urn": school["urn"], "name": school["name"],
        "borough": school["borough"], "website": school["website"],
        "website_class": CLASS_UNVERIFIABLE, "evidence_term": "",
        "evidence_url": "", "evidence_context": "",
        "pages_fetched": 0, "fetch_note": "",
    }
    url = normalise_site_url(school["website"])
    if not url:
        base["fetch_note"] = "no website in GIAS"
        return base

    home = fetcher.get(url)
    if not home.ok:
        base["fetch_note"] = f"homepage fetch failed: {home.error or home.status}"
        return base

    home_text = visible_text(home.text)
    if len(home_text) < cfg["min_visible_text_chars"]:
        base["pages_fetched"] = 1
        base["fetch_note"] = "homepage has almost no static text (JS-only site?)"
        return base

    # Build the fetch queue: homepage links that look relevant, then
    # configured guess-paths as a fallback.
    home_url = home.url  # after redirects
    queue = candidate_links(home.text, home_url, cfg)
    for p in cfg["candidate_paths"]:
        guess = urljoin(home_url.rstrip("/") + "/", p)
        if guess not in queue:
            queue.append(guess)

    breakfast_hit: tuple[str, str, str] | None = None  # (term, url, ctx)
    pages = 1
    kind, term, ctx = find_signals(home_text, cfg)
    if kind == "afterschool":
        base.update(website_class=CLASS_CONFIRMED, evidence_term=term,
                    evidence_url=home_url, evidence_context=ctx,
                    pages_fetched=pages)
        return base
    if kind == "breakfast":
        breakfast_hit = (term, home_url, ctx)

    for page_url in queue[: cfg["max_pages_per_site"] - 1]:
        resp = fetcher.get(page_url)
        pages += 1
        if not resp.ok:
            continue
        text = visible_text(resp.text)
        kind, term, ctx = find_signals(text, cfg)
        if kind == "afterschool":
            base.update(website_class=CLASS_CONFIRMED, evidence_term=term,
                        evidence_url=resp.url, evidence_context=ctx,
                        pages_fetched=pages)
            return base
        if kind == "breakfast" and breakfast_hit is None:
            breakfast_hit = (term, resp.url, ctx)

    base["pages_fetched"] = pages
    if breakfast_hit:
        base.update(website_class=CLASS_BREAKFAST,
                    evidence_term=breakfast_hit[0],
                    evidence_url=breakfast_hit[1],
                    evidence_context=breakfast_hit[2])
    else:
        base["website_class"] = CLASS_NO_EVIDENCE
    return base


def sweep_all(schools: list[dict], cfg: dict, fetcher,
              out_path: Path) -> dict[str, dict]:
    results: dict[str, dict] = {}
    rows = []
    for i, school in enumerate(schools, 1):
        row = sweep_school(school, cfg, fetcher)
        results[school["urn"]] = row
        rows.append(row)
        if i % 25 == 0 or i == len(schools):
            log.info("websweep progress: %d/%d", i, len(schools))
    counts = {}
    for r in rows:
        counts[r["website_class"]] = counts.get(r["website_class"], 0) + 1
    log.info("websweep classes: %s", counts)
    write_csv(out_path, rows, SWEEP_FIELDS)
    return results
