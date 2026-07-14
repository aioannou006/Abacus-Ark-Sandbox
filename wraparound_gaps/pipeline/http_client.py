"""Polite HTTP fetcher: global rate limit, UA, retries, robots.txt.

All network access in the pipeline goes through a Fetcher so the fixture
mode can swap in FakeFetcher and run the whole pipeline offline.
"""

import time
import urllib.robotparser
from urllib.parse import urlparse

from .util import log


class FetchResult:
    def __init__(self, url: str, status: int | None, text: str = "",
                 content: bytes = b"", error: str = ""):
        self.url = url
        self.status = status
        self.text = text
        self.content = content
        self.error = error

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and not self.error


class PoliteFetcher:
    def __init__(self, cfg: dict):
        import requests  # deferred so fixture mode needs no network deps

        self._requests = requests
        self.session = requests.Session()
        self.session.headers["User-Agent"] = cfg["user_agent"]
        self.min_interval = cfg["request_min_interval_s"]
        self.timeout = cfg["request_timeout_s"]
        self.retries = cfg["request_retries"]
        self.respect_robots = cfg["respect_robots_txt"]
        self._last_request_at = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.ua = cfg["user_agent"]

    def _throttle(self) -> None:
        wait = self._last_request_at + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _robots_allows(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._throttle()
                resp = self.session.get(
                    f"{urlparse(url).scheme}://{host}/robots.txt",
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # no usable robots.txt -> allow
            except Exception:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return rp is None or rp.can_fetch(self.ua, url)

    def get(self, url: str, binary: bool = False,
            check_robots: bool = True) -> FetchResult:
        # check_robots=False is reserved for direct downloads of published
        # open-data files (GIAS/Ofsted): those hosts blanket-disallow
        # crawlers in robots.txt even though the files are published for
        # download, and fetching one named file is navigation, not crawling.
        # The school-website sweep always keeps the robots check.
        if check_robots and not self._robots_allows(url):
            log.info("robots.txt disallows %s — skipping", url)
            return FetchResult(url, None, error="blocked by robots.txt")
        last_err = ""
        for attempt in range(self.retries + 1):
            try:
                self._throttle()
                resp = self.session.get(url, timeout=self.timeout)
                return FetchResult(
                    url=str(resp.url),
                    status=resp.status_code,
                    text="" if binary else resp.text,
                    content=resp.content if binary else b"",
                )
            except self._requests.RequestException as e:
                last_err = f"{type(e).__name__}: {e}"
                log.warning("fetch failed (%d/%d) %s: %s",
                            attempt + 1, self.retries + 1, url, last_err)
        return FetchResult(url, None, error=last_err)
