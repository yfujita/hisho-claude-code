"""Tests for main module.

MCPツールハンドラーのヘルパー関数をテストします。
"""

from datetime import datetime
from unittest.mock import MagicMock
import sys

import pytest

# mcpモジュールをモック
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.server'] = MagicMock()
sys.modules['mcp.server.stdio'] = MagicMock()
sys.modules['mcp.types'] = MagicMock()

from src.main import (
    format_event_detail,
    format_event_summary,
    format_event_time,
    get_event_date,
    parse_datetime,
)
from src.models import CalendarEvent, EventDateTime


class TestParseDatetime:
    """parse_datetime関数のテスト."""

    def test_parse_iso8601_with_timezone(self) -> None:
        """タイムゾーン付きISO 8601形式の日時をパースできることを確認."""
        dt_str = "2026-02-05T14:00:00+09:00"
        dt = parse_datetime(dt_str)
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 5
        assert dt.hour == 14
        assert dt.minute == 0

    def test_parse_iso8601_with_z_suffix(self) -> None:
        """Z suffix（UTC）付きISO 8601形式の日時をパースできることを確認."""
        dt_str = "2026-02-05T05:00:00Z"
        dt = parse_datetime(dt_str)
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 5
        assert dt.hour == 5

    def test_parse_invalid_format(self) -> None:
        """不正な形式の日時でValueErrorが発生することを確認."""
        with pytest.raises(ValueError) as exc_info:
            parse_datetime("2026/02/05 14:00:00")
        assert "ISO 8601形式" in str(exc_info.value)


class TestGetEventDate:
    """get_event_date関数のテスト."""

    def test_get_date_from_datetime_event(self, sample_event: CalendarEvent) -> None:
        """日時指定イベントから日付を取得できることを確認."""
        event_date = get_event_date(sample_event)
        assert event_date.year == 2026
        assert event_date.month == 2
        assert event_date.day == 5

    def test_get_date_from_all_day_event(self) -> None:
        """終日イベントから日付を取得できることを確認."""
        event = CalendarEvent(
            id="allday",
            start=EventDateTime(date="2026-02-10"),
            end=EventDateTime(date="2026-02-11"),
            status="confirmed",
            html_link="https://example.com",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        event_date = get_event_date(event)
        assert event_date.year == 2026
        assert event_date.month == 2
        assert event_date.day == 10


class TestFormatEventTime:
    """format_event_time関数のテスト."""

    def test_format_datetime_event(self) -> None:
        """日時指定イベントの時刻をフォーマットできることを確認."""
        event_dt = EventDateTime(
            date_time=datetime(2026, 2, 5, 14, 30, 0),
            time_zone="Asia/Tokyo",
        )
        formatted = format_event_time(event_dt)
        assert formatted == "2026-02-05 14:30"

    def test_format_all_day_event(self) -> None:
        """終日イベントの日付をフォーマットできることを確認."""
        event_dt = EventDateTime(date="2026-02-10")
        formatted = format_event_time(event_dt)
        assert formatted == "2026-02-10"

    def test_format_empty_event_time(self) -> None:
        """日時情報がない場合のフォーマットを確認."""
        event_dt = EventDateTime()
        formatted = format_event_time(event_dt)
        assert "日時不明" in formatted


class TestFormatEventSummary:
    """format_event_summary関数のテスト."""

    def test_format_summary_with_all_fields(self, sample_event: CalendarEvent) -> None:
        """全フィールドを含むイベント概要をフォーマットできることを確認."""
        summary = format_event_summary(sample_event)
        assert "ミーティング" in summary
        assert "会議室A" in summary
        assert "event123abc" in summary

    def test_format_summary_without_title(self) -> None:
        """タイトルがないイベントの概要をフォーマットできることを確認."""
        event = CalendarEvent(
            id="notitle",
            start=EventDateTime(date="2026-02-10"),
            end=EventDateTime(date="2026-02-11"),
            status="confirmed",
            html_link="https://example.com",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        summary = format_event_summary(event)
        assert "タイトルなし" in summary


class TestFormatEventDetail:
    """format_event_detail関数のテスト."""

    def test_format_detail_with_all_fields(self, sample_event: CalendarEvent) -> None:
        """全フィールドを含むイベント詳細をフォーマットできることを確認."""
        detail = format_event_detail(sample_event)
        assert "ミーティング" in detail
        assert "会議室A" in detail
        assert "重要な会議" in detail
        assert "confirmed" in detail
        assert sample_event.html_link in detail

    def test_format_detail_minimal_event(self) -> None:
        """最小限のフィールドを持つイベント詳細をフォーマットできることを確認."""
        event = CalendarEvent(
            id="minimal",
            start=EventDateTime(date="2026-02-10"),
            end=EventDateTime(date="2026-02-11"),
            status="confirmed",
            html_link="https://example.com",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        detail = format_event_detail(event)
        assert "タイトルなし" in detail
        assert "confirmed" in detail
