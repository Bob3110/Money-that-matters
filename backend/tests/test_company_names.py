from app.company_names import find_tickers_by_company_name, _normalize


class TestNormalize:
    def test_strips_inc_suffix(self):
        assert _normalize("Apple Inc.") == "apple"

    def test_strips_corporation_suffix(self):
        assert _normalize("Microsoft Corporation") == "microsoft"

    def test_strips_the_prefix_and_group_suffix(self):
        result = _normalize("The Goldman Sachs Group")
        assert "goldman sachs" in result


class TestFindTickersByCompanyName:
    def test_matches_real_company_name_in_headline(self):
        found = find_tickers_by_company_name(
            "Apple reports record quarterly revenue", frozenset({"AAPL", "MSFT"})
        )
        assert "AAPL" in found

    def test_does_not_match_ticker_not_in_tracked_universe(self):
        found = find_tickers_by_company_name(
            "Apple reports record quarterly revenue", frozenset({"MSFT"})
        )
        assert "AAPL" not in found

    def test_no_false_positive_on_unrelated_headline(self):
        found = find_tickers_by_company_name(
            "Local weather turns colder this weekend", frozenset({"AAPL", "MSFT"})
        )
        assert found == set()

    def test_partial_word_does_not_false_positive(self):
        # "Appleton" should not match "Apple"
        found = find_tickers_by_company_name(
            "Appleton reports new zoning plan", frozenset({"AAPL"})
        )
        assert "AAPL" not in found
