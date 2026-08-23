from app.allowlist import (
    US_MARKET_NEWS_ALLOWLIST,
    matches_allowlist,
    registrable_host,
    source_gate_egypt,
    source_gate_us,
)


class TestRegistrableHost:
    def test_strips_www(self):
        assert registrable_host("https://www.reuters.com/markets/x") == "reuters.com"

    def test_keeps_subdomain(self):
        assert registrable_host("https://markets.reuters.com/x") == "markets.reuters.com"

    def test_strips_port(self):
        assert registrable_host("https://reuters.com:443/x") == "reuters.com"


class TestAdversarialHostMatching:
    def test_lookalike_domain_notreuters_rejected(self):
        assert source_gate_us("https://notreuters.com/fake-article") is None

    def test_suffix_spoof_rejected(self):
        assert source_gate_us("https://reuters.com.spam.tld/fake-article") is None

    def test_subdomain_of_real_host_accepted(self):
        assert source_gate_us("https://markets.reuters.com/real-article") == "Reuters"

    def test_www_prefix_accepted(self):
        assert source_gate_us("https://www.cnbc.com/2026/08/22/story.html") == "CNBC"

    def test_path_containing_hostname_string_does_not_fool_it(self):
        # A URL whose PATH contains "reuters.com" but whose HOST is
        # something else entirely must not match.
        assert source_gate_us("https://evil.example.com/reuters.com/fake") is None

    def test_unlisted_outlet_rejected(self):
        assert source_gate_us("https://www.buzzfeed.com/article") is None

    def test_exact_domain_match(self):
        assert source_gate_us("https://bloomberg.com/news/x") == "Bloomberg"
        assert source_gate_us("https://wsj.com/articles/x") == "The Wall Street Journal"

    def test_sec_gov_accepted_as_press_release_source(self):
        assert source_gate_us("https://www.sec.gov/Archives/edgar/data/x") == "SEC (company filing)"


class TestEgyptAllowlist:
    def test_egx_official_accepted(self):
        assert source_gate_egypt("https://www.egx.com.eg/en/disclosure.aspx") == "The Egyptian Exchange (EGX)"

    def test_enterprise_accepted(self):
        assert source_gate_egypt("https://enterprise.press/story") == "Enterprise"

    def test_international_wire_shared_with_us_list(self):
        assert source_gate_egypt("https://www.reuters.com/world/africa/egypt") == "Reuters"

    def test_lookalike_egyptian_domain_rejected(self):
        assert source_gate_egypt("https://egx-com.eg.fake-mirror.tld/x") is None

    def test_unlisted_outlet_rejected(self):
        assert source_gate_egypt("https://randomblog.com/egypt-stocks") is None


class TestMatchesAllowlistGeneric:
    def test_empty_url_returns_none(self):
        assert matches_allowlist("", US_MARKET_NEWS_ALLOWLIST) is None

    def test_malformed_url_returns_none(self):
        assert matches_allowlist("not a url at all", US_MARKET_NEWS_ALLOWLIST) is None
