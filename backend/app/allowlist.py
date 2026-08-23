"""
Credible-source allow-lists and host-boundary matching.

Every news-style feed (Market News, Egypt News) must enforce one of these.
Matching is done on the URL's registrable host, never substring-on-string --
"notreuters.com" and "reuters.com.spam.tld" must NOT pass as Reuters. See
test_allowlist.py for the adversarial cases this guards against.
"""

from __future__ import annotations

from urllib.parse import urlparse

# host -> display name. Hosts are the registrable domain (and known
# subdomains); matching allows exact match or "ends with .<host>" so that
# e.g. "www.reuters.com" and "markets.reuters.com" match "reuters.com" but
# "reuters.com.evil.tld" and "notreuters.com" do not.
US_MARKET_NEWS_ALLOWLIST: dict[str, str] = {
    "reuters.com": "Reuters",
    "cnbc.com": "CNBC",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "The Wall Street Journal",
    "sec.gov": "SEC (company filing)",
}

EGYPT_NEWS_ALLOWLIST: dict[str, str] = {
    # Egyptian business/financial press + official bodies
    "egx.com.eg": "The Egyptian Exchange (EGX)",
    "cbe.org.eg": "Central Bank of Egypt",
    "capmas.gov.eg": "CAPMAS",
    "enterprise.press": "Enterprise",
    "mubasher.info": "Mubasher",
    "almalnews.com": "Al-Mal",
    "alborsaanews.com": "Al-Borsa",
    "almasryalyoum.com": "Al-Masry Al-Youm",
    "shorouknews.com": "Al-Shorouk",
    "ahram.org.eg": "Al-Ahram",
    "dailynewsegypt.com": "Daily News Egypt",
    # international wires, same standard as US allow-list
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "wsj.com": "The Wall Street Journal",
    "zawya.com": "Zawya",
    "apnews.com": "AP",
}


def registrable_host(url: str) -> str:
    """Extract a lowercase host from a URL, stripping a leading 'www.'."""
    netloc = urlparse(url).netloc.lower()
    # strip userinfo/port if present
    netloc = netloc.split("@")[-1].split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def matches_allowlist(url: str, allowlist: dict[str, str]) -> str | None:
    """Return the display name if `url`'s host is on (or a subdomain of) an
    allow-listed host, else None. Never does substring matching on the raw
    string -- always splits on host boundaries."""
    host = registrable_host(url)
    if not host:
        return None
    for allowed_host, name in allowlist.items():
        if host == allowed_host or host.endswith("." + allowed_host):
            return name
    return None


def source_gate_us(url: str) -> str | None:
    return matches_allowlist(url, US_MARKET_NEWS_ALLOWLIST)


def source_gate_egypt(url: str) -> str | None:
    return matches_allowlist(url, EGYPT_NEWS_ALLOWLIST)
