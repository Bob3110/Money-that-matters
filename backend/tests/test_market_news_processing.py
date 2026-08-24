import pytest

from app.fetchers.market_news import process_feed_entry, reset_and_snapshot_reject_stats


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
