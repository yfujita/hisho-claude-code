"""Pytest configuration and fixtures.

このモジュールは、テスト全体で使用される共通のフィクスチャを定義します。
"""

from datetime import datetime, timedelta

import pytest

from src.config import GoogleCalendarConfig
from src.models import Attendee, CalendarEvent, EventDateTime
from src.rate_limiter import RateLimiter


@pytest.fixture
def mock_config() -> GoogleCalendarConfig:
    """モックのGoogle Calendar設定を返す.

    Returns:
        GoogleCalendarConfig: テスト用の設定
    """
    # 環境変数を使わずに直接設定を作成
    # 実際のクライアントID/シークレットは不要（テストではモックを使用）
    return GoogleCalendarConfig(
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="test-client-secret-xxxxxxxxxxxxxxxx",
        google_refresh_token="test-refresh-token-xxxxxxxxxxxxxxxx",
        google_access_token="test-access-token-xxxxxxxxxxxxxxxx",
        google_calendar_id="primary",
        google_calendar_timezone="Asia/Tokyo",
        mcp_log_level="DEBUG",
    )


@pytest.fixture
def rate_limiter() -> RateLimiter:
    """レート制限のインスタンスを返す.

    Returns:
        RateLimiter: テスト用のレート制限（高速設定）
    """
    # テスト用に高速なレート制限を設定
    return RateLimiter(tokens_per_second=100.0, capacity=10)


@pytest.fixture
def sample_event_dict() -> dict:
    """サンプルイベントデータ（API形式）を返す.

    Returns:
        dict: Google Calendar APIレスポンス形式のイベントデータ
    """
    return {
        "id": "event123abc",
        "summary": "ミーティング",
        "description": "重要な会議",
        "location": "会議室A",
        "start": {
            "dateTime": "2026-02-05T14:00:00+09:00",
            "timeZone": "Asia/Tokyo",
        },
        "end": {
            "dateTime": "2026-02-05T15:00:00+09:00",
            "timeZone": "Asia/Tokyo",
        },
        "status": "confirmed",
        "attendees": [
            {
                "email": "user1@example.com",
                "displayName": "User 1",
                "responseStatus": "accepted",
                "organizer": True,
            },
            {
                "email": "user2@example.com",
                "displayName": "User 2",
                "responseStatus": "needsAction",
            },
        ],
        "htmlLink": "https://www.google.com/calendar/event?eid=event123abc",
        "created": "2026-02-01T10:00:00.000Z",
        "updated": "2026-02-02T15:30:00.000Z",
        "creatorEmail": "creator@example.com",
        "organizerEmail": "organizer@example.com",
    }


@pytest.fixture
def sample_event() -> CalendarEvent:
    """サンプルイベントモデルを返す.

    Returns:
        CalendarEvent: テスト用のイベントモデル
    """
    return CalendarEvent(
        id="event123abc",
        summary="ミーティング",
        description="重要な会議",
        location="会議室A",
        start=EventDateTime(
            date_time=datetime(2026, 2, 5, 14, 0, 0),
            time_zone="Asia/Tokyo",
        ),
        end=EventDateTime(
            date_time=datetime(2026, 2, 5, 15, 0, 0),
            time_zone="Asia/Tokyo",
        ),
        status="confirmed",
        attendees=[
            Attendee(
                email="user1@example.com",
                display_name="User 1",
                response_status="accepted",
                organizer=True,
            ),
            Attendee(
                email="user2@example.com",
                display_name="User 2",
                response_status="needsAction",
            ),
        ],
        html_link="https://www.google.com/calendar/event?eid=event123abc",
        created=datetime(2026, 2, 1, 10, 0, 0),
        updated=datetime(2026, 2, 2, 15, 30, 0),
        creator_email="creator@example.com",
        organizer_email="organizer@example.com",
    )


@pytest.fixture
def sample_all_day_event_dict() -> dict:
    """終日イベントのサンプルデータ（API形式）を返す.

    Returns:
        dict: Google Calendar APIレスポンス形式の終日イベントデータ
    """
    return {
        "id": "allday123",
        "summary": "終日イベント",
        "start": {
            "date": "2026-02-10",
        },
        "end": {
            "date": "2026-02-11",
        },
        "status": "confirmed",
        "htmlLink": "https://www.google.com/calendar/event?eid=allday123",
        "created": "2026-02-01T10:00:00.000Z",
        "updated": "2026-02-01T10:00:00.000Z",
    }


@pytest.fixture
def mock_token_response() -> dict:
    """モックのトークンレスポンスを返す.

    Returns:
        dict: OAuth2トークンエンドポイントのレスポンス形式
    """
    return {
        "access_token": "new-access-token-xxxxxxxxxxxxxxxx",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/calendar",
    }


@pytest.fixture
def mock_events_list_response(sample_event_dict: dict) -> dict:
    """モックのイベント一覧レスポンスを返す.

    Args:
        sample_event_dict: サンプルイベントデータ

    Returns:
        dict: Google Calendar APIのevents.listレスポンス形式
    """
    return {
        "kind": "calendar#events",
        "etag": "\"test-etag\"",
        "summary": "Primary Calendar",
        "updated": "2026-02-04T10:00:00.000Z",
        "timeZone": "Asia/Tokyo",
        "accessRole": "owner",
        "defaultReminders": [],
        "items": [sample_event_dict],
    }
