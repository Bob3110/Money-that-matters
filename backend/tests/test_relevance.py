from app.relevance import (
    is_valid_us_ticker,
    passes_egypt_subject_gate,
    passes_us_subject_gate,
)


class TestUsSubjectGate:
    def test_named_ticker_passes(self):
        assert passes_us_subject_gate(
            headline="Apple beats earnings expectations",
            tracked_tickers={"AAPL", "MSFT"},
            mentioned_tickers={"AAPL"},
            is_markets_business_desk=False,
        )

    def test_untracked_ticker_mention_fails(self):
        assert not passes_us_subject_gate(
            headline="Some obscure micro-cap news",
            tracked_tickers={"AAPL", "MSFT"},
            mentioned_tickers={"ZZZZ"},
            is_markets_business_desk=False,
        )

    def test_markets_desk_with_relevant_term_passes(self):
        assert passes_us_subject_gate(
            headline="Fed signals possible rate cut at next meeting",
            tracked_tickers={"AAPL"},
            mentioned_tickers=set(),
            is_markets_business_desk=True,
        )

    def test_markets_desk_without_relevant_term_fails(self):
        assert not passes_us_subject_gate(
            headline="Local team wins championship game",
            tracked_tickers={"AAPL"},
            mentioned_tickers=set(),
            is_markets_business_desk=True,
        )

    def test_general_world_news_from_allowlisted_outlet_still_fails(self):
        # A war story from Reuters clears the SOURCE gate but must fail
        # this subject gate -- the source gate controls who's credible,
        # not what's relevant.
        assert not passes_us_subject_gate(
            headline="Ceasefire talks continue amid regional tensions",
            tracked_tickers={"AAPL"},
            mentioned_tickers=set(),
            is_markets_business_desk=False,
        )

    def test_referendum_story_fails_even_from_business_desk_without_market_term(self):
        assert not passes_us_subject_gate(
            headline="Country holds referendum on constitutional reform",
            tracked_tickers={"AAPL"},
            mentioned_tickers=set(),
            is_markets_business_desk=True,
        )


class TestEgyptSubjectGate:
    def test_native_outlet_with_finance_term_passes(self):
        assert passes_egypt_subject_gate(
            headline="EGX30 climbs on strong bank earnings",
            outlet_is_native_egyptian=True,
            mentions_egypt_or_egx=True,
        )

    def test_native_outlet_sports_story_fails(self):
        assert not passes_egypt_subject_gate(
            headline="Al Ahly wins derby match 2-1",
            outlet_is_native_egyptian=True,
            mentions_egypt_or_egx=False,
        )

    def test_international_wire_naming_egypt_with_finance_term_passes(self):
        assert passes_egypt_subject_gate(
            headline="Egypt's central bank holds interest rate steady",
            outlet_is_native_egyptian=False,
            mentions_egypt_or_egx=True,
        )

    def test_international_wire_without_naming_egypt_fails(self):
        assert not passes_egypt_subject_gate(
            headline="Central bank holds interest rate steady",
            outlet_is_native_egyptian=False,
            mentions_egypt_or_egx=False,
        )

    def test_arabic_finance_term_recognized(self):
        assert passes_egypt_subject_gate(
            headline="البورصة المصرية ترتفع بدعم من أسهم البنوك",
            outlet_is_native_egyptian=True,
            mentions_egypt_or_egx=True,
        )


class TestTickerValidation:
    def test_normal_ticker_valid(self):
        assert is_valid_us_ticker("AAPL")
        assert is_valid_us_ticker("V")

    def test_lowercase_normalized_and_valid(self):
        assert is_valid_us_ticker("aapl")

    def test_none_rejected(self):
        assert not is_valid_us_ticker(None)

    def test_placeholder_none_string_rejected(self):
        assert not is_valid_us_ticker("NONE")
        assert not is_valid_us_ticker("N/A")
        assert not is_valid_us_ticker("")
        assert not is_valid_us_ticker("-")

    def test_foreign_dual_listing_rejected(self):
        assert not is_valid_us_ticker("ASX:LNW")

    def test_dotted_class_share_rejected(self):
        assert not is_valid_us_ticker("BRK.B")

    def test_too_long_rejected(self):
        assert not is_valid_us_ticker("TOOLONGTICKER")

    def test_numeric_rejected(self):
        assert not is_valid_us_ticker("12345")
