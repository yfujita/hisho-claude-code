"""Pydantic models for Google Calendar API integration.

このモジュールは、Google Calendar APIのレスポンスとリクエストを型安全に扱うための
Pydanticモデルを定義しています。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CalendarEventStatus(str, Enum):
    """カレンダーイベントのステータス.

    Google Calendarで使用されるイベントステータスの値。
    """

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class AttendeeResponseStatus(str, Enum):
    """出席者の返信ステータス.

    イベント招待に対する返信状況を表します。
    """

    NEEDS_ACTION = "needsAction"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"


class EventDateTime(BaseModel):
    """イベントの日時を表すモデル.

    dateTimeとdateは排他的で、どちらか一方のみが設定されます。
    - dateTime: 特定の時刻を持つイベント
    - date: 終日イベント

    Attributes:
        date_time: ISO 8601形式の日時（例: "2026-02-04T10:00:00+09:00"）
        date: ISO 8601形式の日付（例: "2026-02-04"）
        time_zone: タイムゾーン（例: "Asia/Tokyo"）
    """

    date_time: Optional[datetime] = Field(
        None, description="イベントの日時（時刻指定あり）", alias="dateTime"
    )
    date: Optional[str] = Field(None, description="イベントの日付（終日イベント）")
    time_zone: Optional[str] = Field(None, description="タイムゾーン", alias="timeZone")

    model_config = ConfigDict(
        # JSONフィールド名をsnake_caseからcamelCaseに変換
        populate_by_name=True,
        # Google APIのレスポンスフィールド名に対応
        json_schema_extra={
            "examples": [
                {
                    "dateTime": "2026-02-04T10:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                }
            ]
        },
    )


class Attendee(BaseModel):
    """イベント出席者を表すモデル.

    Attributes:
        email: 出席者のメールアドレス
        display_name: 表示名
        response_status: 返信ステータス
        optional: オプション出席者かどうか
        organizer: 主催者かどうか
        self_attendee: 自分自身かどうか
    """

    email: str = Field(..., description="出席者のメールアドレス")
    display_name: Optional[str] = Field(None, description="表示名", alias="displayName")
    response_status: Optional[AttendeeResponseStatus] = Field(
        None, description="返信ステータス", alias="responseStatus"
    )
    optional: bool = Field(False, description="オプション出席者かどうか")
    organizer: bool = Field(False, description="主催者かどうか")
    self_attendee: bool = Field(False, description="自分自身かどうか", alias="self")

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
    )


class CalendarEvent(BaseModel):
    """カレンダーイベントを表すモデル.

    Google Calendarのイベントデータを表現するモデル。
    Google Calendar APIのレスポンスから必要な情報を抽出して保持します。

    Attributes:
        id: イベントID
        summary: イベントのタイトル
        description: イベントの説明
        location: 場所
        start: 開始日時
        end: 終了日時
        status: ステータス
        attendees: 出席者リスト
        html_link: GoogleカレンダーのWebページURL
        created: 作成日時
        updated: 最終更新日時
        creator_email: 作成者のメールアドレス
        organizer_email: 主催者のメールアドレス
        recurrence: 繰り返しルール（RRULE形式）
        hangout_link: Google Meetのリンク
    """

    id: str = Field(..., description="イベントID")
    summary: Optional[str] = Field(None, description="イベントのタイトル")
    description: Optional[str] = Field(None, description="イベントの説明")
    location: Optional[str] = Field(None, description="場所")
    start: EventDateTime = Field(..., description="開始日時")
    end: EventDateTime = Field(..., description="終了日時")
    status: CalendarEventStatus = Field(..., description="ステータス")
    attendees: list[Attendee] = Field(default_factory=list, description="出席者リスト")
    html_link: str = Field(..., description="GoogleカレンダーのWebページURL", alias="htmlLink")
    created: datetime = Field(..., description="作成日時")
    updated: datetime = Field(..., description="最終更新日時")
    creator_email: Optional[str] = Field(None, description="作成者のメールアドレス", alias="creatorEmail")
    organizer_email: Optional[str] = Field(None, description="主催者のメールアドレス", alias="organizerEmail")
    recurrence: list[str] = Field(default_factory=list, description="繰り返しルール")
    hangout_link: Optional[str] = Field(None, description="Google Meetのリンク", alias="hangoutLink")

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
    )


class GoogleCalendarError(BaseModel):
    """Google Calendar APIのエラーレスポンス.

    API呼び出しが失敗した際のエラー情報を表現するモデル。

    Attributes:
        code: HTTPステータスコード
        message: エラーメッセージ
        status: エラーステータス
        errors: 詳細なエラー情報のリスト
    """

    code: int = Field(..., description="HTTPステータスコード")
    message: str = Field(..., description="エラーメッセージ")
    status: str = Field(..., description="エラーステータス")
    errors: list[dict] = Field(default_factory=list, description="詳細なエラー情報")
