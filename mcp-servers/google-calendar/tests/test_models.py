"""Tests for models module.

Pydanticモデルのバリデーションとシリアライゼーションをテストします。
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models import (
    Attendee,
    AttendeeResponseStatus,
    CalendarEvent,
    CalendarEventStatus,
    EventDateTime,
    GoogleCalendarError,
)


class TestCalendarEventStatus:
    """CalendarEventStatus enumのテスト."""

    def test_all_status_values(self) -> None:
        """すべてのステータス値が正しく定義されていることを確認."""
        assert CalendarEventStatus.CONFIRMED.value == "confirmed"
        assert CalendarEventStatus.TENTATIVE.value == "tentative"
        assert CalendarEventStatus.CANCELLED.value == "cancelled"

    def test_status_from_string(self) -> None:
        """文字列からステータスを作成できることを確認."""
        status = CalendarEventStatus("confirmed")
        assert status == CalendarEventStatus.CONFIRMED

    def test_invalid_status(self) -> None:
        """無効なステータス値でエラーが発生することを確認."""
        with pytest.raises(ValueError):
            CalendarEventStatus("invalid_status")


class TestAttendeeResponseStatus:
    """AttendeeResponseStatus enumのテスト."""

    def test_all_response_status_values(self) -> None:
        """すべての返信ステータス値が正しく定義されていることを確認."""
        assert AttendeeResponseStatus.NEEDS_ACTION.value == "needsAction"
        assert AttendeeResponseStatus.DECLINED.value == "declined"
        assert AttendeeResponseStatus.TENTATIVE.value == "tentative"
        assert AttendeeResponseStatus.ACCEPTED.value == "accepted"

    def test_response_status_from_string(self) -> None:
        """文字列から返信ステータスを作成できることを確認."""
        status = AttendeeResponseStatus("accepted")
        assert status == AttendeeResponseStatus.ACCEPTED


class TestEventDateTime:
    """EventDateTimeモデルのテスト."""

    def test_create_with_datetime(self) -> None:
        """日時指定ありのEventDateTimeを作成できることを確認."""
        event_dt = EventDateTime(
            date_time=datetime(2026, 2, 5, 14, 0, 0),
            time_zone="Asia/Tokyo",
        )
        assert event_dt.date_time == datetime(2026, 2, 5, 14, 0, 0)
        assert event_dt.time_zone == "Asia/Tokyo"
        assert event_dt.date is None

    def test_create_with_date_only(self) -> None:
        """終日イベント（日付のみ）のEventDateTimeを作成できることを確認."""
        event_dt = EventDateTime(date="2026-02-10")
        assert event_dt.date == "2026-02-10"
        assert event_dt.date_time is None

    def test_both_date_and_datetime_can_coexist(self) -> None:
        """dateとdate_timeの両方が設定できることを確認（APIレスポンスでは排他的）."""
        # モデルとしては両方設定できるが、実際のAPIレスポンスでは排他的
        event_dt = EventDateTime(
            date_time=datetime(2026, 2, 5, 14, 0, 0),
            date="2026-02-05",
        )
        assert event_dt.date_time is not None
        assert event_dt.date is not None


class TestAttendee:
    """Attendeeモデルのテスト."""

    def test_create_with_all_fields(self) -> None:
        """全フィールドを指定してAttendeeを作成できることを確認."""
        attendee = Attendee(
            email="user@example.com",
            display_name="Test User",
            response_status=AttendeeResponseStatus.ACCEPTED,
            optional=False,
            organizer=True,
            self_attendee=False,
        )
        assert attendee.email == "user@example.com"
        assert attendee.display_name == "Test User"
        assert attendee.response_status == AttendeeResponseStatus.ACCEPTED
        assert attendee.organizer is True
        assert attendee.optional is False

    def test_create_with_minimal_fields(self) -> None:
        """最小限のフィールドでAttendeeを作成できることを確認."""
        attendee = Attendee(email="minimal@example.com")
        assert attendee.email == "minimal@example.com"
        assert attendee.display_name is None
        assert attendee.response_status is None
        assert attendee.optional is False
        assert attendee.organizer is False

    def test_missing_email_raises_error(self) -> None:
        """メールアドレスが欠けている場合にエラーが発生することを確認."""
        with pytest.raises(ValidationError):
            Attendee()


class TestCalendarEvent:
    """CalendarEventモデルのテスト."""

    def test_create_with_all_fields(self, sample_event: CalendarEvent) -> None:
        """全フィールドを指定してCalendarEventを作成できることを確認."""
        assert sample_event.id == "event123abc"
        assert sample_event.summary == "ミーティング"
        assert sample_event.description == "重要な会議"
        assert sample_event.location == "会議室A"
        assert sample_event.status == CalendarEventStatus.CONFIRMED
        assert len(sample_event.attendees) == 2
        assert sample_event.html_link == "https://www.google.com/calendar/event?eid=event123abc"

    def test_create_from_api_dict(self, sample_event_dict: dict) -> None:
        """API形式のdictからCalendarEventを作成できることを確認."""
        event = CalendarEvent(**sample_event_dict)
        assert event.id == sample_event_dict["id"]
        assert event.summary == sample_event_dict["summary"]
        assert event.location == sample_event_dict["location"]
        assert event.status.value == sample_event_dict["status"]

    def test_create_minimal_event(self) -> None:
        """最小限のフィールドでCalendarEventを作成できることを確認."""
        event = CalendarEvent(
            id="minimal-event",
            start=EventDateTime(date="2026-02-10"),
            end=EventDateTime(date="2026-02-11"),
            status=CalendarEventStatus.CONFIRMED,
            html_link="https://example.com",
            created=datetime(2026, 2, 1, 10, 0, 0),
            updated=datetime(2026, 2, 1, 10, 0, 0),
        )
        assert event.id == "minimal-event"
        assert event.summary is None
        assert event.description is None
        assert event.location is None
        assert event.attendees == []

    def test_missing_required_fields(self) -> None:
        """必須フィールドが欠けている場合にエラーが発生することを確認."""
        # idが欠けている
        with pytest.raises(ValidationError):
            CalendarEvent(
                start=EventDateTime(date="2026-02-10"),
                end=EventDateTime(date="2026-02-11"),
                status=CalendarEventStatus.CONFIRMED,
                html_link="https://example.com",
                created=datetime.now(),
                updated=datetime.now(),
            )

        # startが欠けている
        with pytest.raises(ValidationError):
            CalendarEvent(
                id="test-id",
                end=EventDateTime(date="2026-02-11"),
                status=CalendarEventStatus.CONFIRMED,
                html_link="https://example.com",
                created=datetime.now(),
                updated=datetime.now(),
            )

    def test_model_dump_excludes_none(self, sample_event: CalendarEvent) -> None:
        """model_dumpでNone値が除外されることを確認."""
        # recurrenceやhangout_linkがNoneの場合
        event = CalendarEvent(
            id="test",
            summary="Test Event",
            start=EventDateTime(date="2026-02-10"),
            end=EventDateTime(date="2026-02-11"),
            status=CalendarEventStatus.CONFIRMED,
            html_link="https://example.com",
            created=datetime.now(),
            updated=datetime.now(),
            hangout_link=None,  # None
        )
        dumped = event.model_dump(exclude_none=True)
        assert "hangout_link" not in dumped
        assert "recurrence" in dumped  # default_factory=listなので含まれる


class TestGoogleCalendarError:
    """GoogleCalendarErrorモデルのテスト."""

    def test_create_calendar_error(self) -> None:
        """GoogleCalendarErrorを作成できることを確認."""
        error = GoogleCalendarError(
            code=400,
            message="Invalid request",
            status="INVALID_ARGUMENT",
            errors=[
                {
                    "domain": "global",
                    "reason": "invalid",
                    "message": "Invalid value",
                }
            ],
        )
        assert error.code == 400
        assert error.message == "Invalid request"
        assert error.status == "INVALID_ARGUMENT"
        assert len(error.errors) == 1

    def test_error_with_minimal_fields(self) -> None:
        """最小限のフィールドでGoogleCalendarErrorを作成できることを確認."""
        error = GoogleCalendarError(
            code=404,
            message="Not found",
            status="NOT_FOUND",
        )
        assert error.code == 404
        assert error.message == "Not found"
        assert error.errors == []

    def test_missing_required_field(self) -> None:
        """必須フィールドが欠けている場合にエラーが発生することを確認."""
        with pytest.raises(ValidationError):
            GoogleCalendarError(
                code=400,
                message="Invalid request",
                # statusが欠けている
            )
