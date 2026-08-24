import pytest

from app.fetchers.market_news import _extract_tickers, process_feed_entry, reset_and_snapshot_reject_stats


@pytest.mark.asyncio
class TestProcessFeedEntryLinkFallback:
    async def test_missing_link_field_uses_id_fallback(self):
        # Regression test: switching CNBC endpoints produced feed entries
        # where 'link' was empty but the article URL was present under a
        # different feedparser field ('id'/'guid'). Every one of 90 real
        # entries silently failed the source gate on an empty link before
        # this fallback existed, with zero visibility into why.
        reset_and_snapshot_reject_stats()
        entry = {
            "title": "Apple reports strong quarterly earnings",
            "id": "https://www.cnbc.com/2026/08/24/apple-earnings.html",
            "published": "2026-08-24T12:00:00Z",
        }
        result = await process_feed_entry(entry, "CNBC (Earnings)", is_markets_business_desk=True)
        assert result is not None
        assert result["source_url"] == "https://www.cnbc.com/2026/08/24/apple-earnings.html"

    async def test_no_link_anywhere_rejected_with_reason(self):
        reset_and_snapshot_reject_stats()
        entry = {"title": "Some headline", "published": "2026-08-24T12:00:00Z"}
        result = await process_feed_entry(entry, "CNBC (Earnings)", is_markets_business_desk=True)
        assert result is None
        stats = reset_and_snapshot_reject_stats()
        assert stats.get("no_link") == 1

    async def test_reject_reasons_are_tallied(self):
        reset_and_snapshot_reject_stats()
        # one with no link, one with an unrecognized source
        await process_feed_entry({"title": "x", "published": "2026-08-24T12:00:00Z"}, "X", True)
        await process_feed_entry(
            {"title": "x", "link": "https://example.com/x", "published": "2026-08-24T12:00:00Z"}, "X", True
        )
        stats = reset_and_snapshot_reject_stats()
        assert stats.get("no_link") == 1
        assert stats.get("source_gate") == 1


@pytest.mark.asyncio
class TestPublishedAtResolution:
    async def test_uses_feedparser_parsed_struct_when_available(self):
        # Regression test: switching CNBC endpoints surfaced RFC 822 dates
        # (the actual RSS 2.0 <pubDate> standard) that dates.py's original
        # three formats never covered -- 100% of real items failed with
        # 'unparseable_date' until this preference for feedparser's own
        # normalized struct existed.
        reset_and_snapshot_reject_stats()
        entry = {
            "title": "Apple reports strong quarterly earnings",
            "link": "https://www.cnbc.com/2026/08/24/apple-earnings.html",
            "published": "Mon, 24 Aug 2026 12:00:00 GMT",
            "published_parsed": (2026, 8, 24, 12, 0, 0, 0, 0, 0),
        }
        result = await process_feed_entry(entry, "CNBC (Earnings)", is_markets_business_desk=True)
        assert result is not None
        assert result["published_at"].year == 2026
        assert result["published_at"].month == 8
        assert result["published_at"].day == 24

    async def test_falls_back_to_raw_string_without_parsed_struct(self):
        reset_and_snapshot_reject_stats()
        entry = {
            "title": "Apple reports strong quarterly earnings",
            "link": "https://www.cnbc.com/2026/08/24/apple-earnings.html",
            "published": "2026-08-24T12:00:00Z",
        }
        result = await process_feed_entry(entry, "CNBC (Earnings)", is_markets_business_desk=True)
        assert result is not None
        assert result["published_at"].day == 24


class TestExtractTickersSingleLetterFalsePositive:
    def test_single_letter_ticker_not_matched_as_word(self):
        # Regression test: a real live headline "A media M&A chill: the
        # Paramount-WBD antitrust challenge..." was tagged with ticker
        # "A" (Agilent's real symbol) purely because "A" is also the
        # English indefinite article -- a false positive with zero
        # relationship to the headline's actual content.
        found = _extract_tickers(
            "A media M&A chill: the Paramount-WBD antitrust challenge",
            frozenset({"A", "WBD"}),
        )
        assert "A" not in found

    def test_single_letter_company_name_still_matched_via_name_path(self):
        # The exclusion is specific to the literal-symbol path -- a real
        # mention of the company's full registered name should still
        # work. Note: the name matcher requires the full normalized name
        # ("Agilent Technologies"), not a short-form mention ("Agilent"
        # alone) -- that's a separate, real precision/recall tradeoff in
        # company_names.py, not something this fix changes.
        found = _extract_tickers("Agilent Technologies reports strong earnings", frozenset({"A"}))
        assert "A" in found

    def test_multi_letter_ticker_still_matched(self):
        found = _extract_tickers("AAPL shares rose today", frozenset({"AAPL"}))
        assert "AAPL" in found
