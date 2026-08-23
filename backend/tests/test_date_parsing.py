import pytest

from app.dates import DateParseError, parse_item_date


class TestThreeObservedFormats:
    def test_iso8601_with_utc_offset(self):
        dt = parse_item_date("2026-08-20T14:03:00+00:00")
        assert dt.year == 2026 and dt.month == 8 and dt.day == 20
        assert dt.tzinfo is not None

    def test_iso8601_with_z_suffix(self):
        dt = parse_item_date("2026-08-20T14:03:00Z")
        assert dt.hour == 14
        assert dt.tzinfo is not None

    def test_iso8601_with_non_utc_offset(self):
        dt = parse_item_date("2026-08-20T14:03:00-05:00")
        assert dt.tzinfo is not None

    def test_plain_iso_date(self):
        dt = parse_item_date("2026-08-20")
        assert (dt.year, dt.month, dt.day) == (2026, 8, 20)
        assert dt.tzinfo is not None  # assumed UTC, documented

    def test_plain_iso_datetime_no_offset(self):
        dt = parse_item_date("2026-08-20T14:03:00")
        assert dt.hour == 14
        assert dt.tzinfo is not None

    def test_us_style_m_d_y(self):
        dt = parse_item_date("8/20/2026")
        assert (dt.year, dt.month, dt.day) == (2026, 8, 20)

    def test_us_style_m_d_y_two_digit_year(self):
        dt = parse_item_date("8/20/26")
        assert dt.year == 2026


class TestFailureModesAreLoudNotSilent:
    def test_empty_string_raises(self):
        with pytest.raises(DateParseError):
            parse_item_date("")

    def test_garbage_string_raises(self):
        with pytest.raises(DateParseError):
            parse_item_date("not a date at all")

    def test_none_like_placeholder_raises(self):
        with pytest.raises(DateParseError):
            parse_item_date("   ")


class TestConsistency:
    def test_same_calendar_date_different_formats_agree(self):
        a = parse_item_date("2026-08-20T00:00:00Z")
        b = parse_item_date("2026-08-20")
        c = parse_item_date("8/20/2026")
        assert a.date() == b.date() == c.date()
