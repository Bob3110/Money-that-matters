from app.fetchers.egypt_news import process_article, reset_and_snapshot_reject_stats


class TestProcessArticle:
    def test_accepts_valid_egyptian_article(self):
        reset_and_snapshot_reject_stats()
        article = {
            "title": "EGX30 climbs on strong bank earnings",
            "url": "https://enterprise.press/story",
            "seendate": "20260824T120000Z",
        }
        result = process_article(article)
        assert result is not None
        assert result["outlet"] == "Enterprise"

    def test_rejects_missing_url_before_calling_source_gate(self):
        # Regression-style test: field-presence checks must run before
        # the source gate, matching the fix applied to market_news.py's
        # process_feed_entry after a missing field there caused a
        # silent, uniform rejection of every item with no diagnosis.
        reset_and_snapshot_reject_stats()
        article = {"title": "Some headline", "seendate": "20260824T120000Z"}
        result = process_article(article)
        assert result is None
        stats = reset_and_snapshot_reject_stats()
        assert stats.get("no_url") == 1

    def test_rejects_unlisted_outlet_with_reason(self):
        reset_and_snapshot_reject_stats()
        article = {
            "title": "EGX30 climbs on strong bank earnings",
            "url": "https://randomblog.example/story",
            "seendate": "20260824T120000Z",
        }
        result = process_article(article)
        assert result is None
        stats = reset_and_snapshot_reject_stats()
        assert stats.get("source_gate") == 1

    def test_rejects_off_topic_article_from_allowlisted_outlet(self):
        reset_and_snapshot_reject_stats()
        article = {
            "title": "Al Ahly wins derby match 2-1",
            "url": "https://enterprise.press/sports-story",
            "seendate": "20260824T120000Z",
        }
        result = process_article(article)
        assert result is None
        stats = reset_and_snapshot_reject_stats()
        assert stats.get("subject_gate") == 1
