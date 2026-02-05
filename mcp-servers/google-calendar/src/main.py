"""MCP Server main entry point for Google Calendar.

このモジュールは、Fast MCPを使用してMCPサーバーを実装し、
Google Calendar連携のツールを公開します。
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .auth import GoogleCalendarAuth
from .calendar_client import GoogleCalendarClient
from .config import GoogleCalendarConfig
from .exceptions import ConfigurationError, GoogleCalendarMCPError
from .logger import setup_logger
from .models import CalendarEvent, EventDateTime

# ロギング設定（環境変数で制御）
log_level = os.getenv("MCP_LOG_LEVEL", "INFO")
use_json_logs = os.getenv("MCP_LOG_JSON", "false").lower() == "true"

logger = setup_logger(
    name="hisho-google-calendar-mcp",
    level=log_level,
    use_json=use_json_logs,
)

# グローバル変数
config: GoogleCalendarConfig
calendar_client: GoogleCalendarClient
server = Server("hisho-google-calendar-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """利用可能なツール一覧を返す.

    Returns:
        list[Tool]: ツールのリスト
    """
    return [
        Tool(
            name="list_calendars",
            description=(
                "Google Calendarのカレンダー一覧を取得します。"
                "アクセス可能なすべてのカレンダーの情報（ID、名前、アクセス権限など）を取得できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_events",
            description=(
                "Google Calendarから予定一覧を取得します。"
                "期間を指定して、その期間内の予定を取得できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": (
                            "カレンダーID。省略時はデフォルトカレンダーを使用します。"
                        ),
                    },
                    "time_min": {
                        "type": "string",
                        "description": (
                            "取得開始日時（ISO 8601形式、例: 2026-02-04T00:00:00+09:00）。"
                            "省略時は現在時刻から取得します。"
                        ),
                    },
                    "time_max": {
                        "type": "string",
                        "description": (
                            "取得終了日時（ISO 8601形式）。"
                            "省略時はtime_minから7日後まで取得します。"
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大取得件数（デフォルト: 10）",
                        "default": 10,
                    },
                },
            },
        ),
        Tool(
            name="get_event",
            description="指定したイベントの詳細情報を取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "イベントID",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": (
                            "カレンダーID。省略時はデフォルトカレンダーを使用します。"
                        ),
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="create_event",
            description=(
                "Google Calendarに新しい予定を作成します。"
                "タイトル、開始・終了日時を指定して予定を作成できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "予定のタイトル",
                    },
                    "start_time": {
                        "type": "string",
                        "description": (
                            "開始日時（ISO 8601形式、例: 2026-02-05T14:00:00+09:00）"
                        ),
                    },
                    "end_time": {
                        "type": "string",
                        "description": "終了日時（ISO 8601形式）",
                    },
                    "location": {
                        "type": "string",
                        "description": "場所（オプション）",
                    },
                    "description": {
                        "type": "string",
                        "description": "詳細説明（オプション）",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": (
                            "カレンダーID。省略時はデフォルトカレンダーを使用します。"
                        ),
                    },
                },
                "required": ["summary", "start_time", "end_time"],
            },
        ),
        Tool(
            name="update_event",
            description="既存の予定を更新します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "更新するイベントのID",
                    },
                    "summary": {
                        "type": "string",
                        "description": "新しいタイトル（オプション）",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "新しい開始日時（ISO 8601形式）（オプション）",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "新しい終了日時（ISO 8601形式）（オプション）",
                    },
                    "location": {
                        "type": "string",
                        "description": "新しい場所（オプション）",
                    },
                    "description": {
                        "type": "string",
                        "description": "新しい詳細説明（オプション）",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": (
                            "カレンダーID。省略時はデフォルトカレンダーを使用します。"
                        ),
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="get_events_from_multiple_calendars",
            description=(
                "複数のGoogle Calendarから予定を一括取得します。"
                "複数のカレンダーの予定をまとめて時系列順に表示できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "カレンダーIDのリスト。省略時はすべてのカレンダーから取得します。"
                        ),
                    },
                    "time_min": {
                        "type": "string",
                        "description": (
                            "取得開始日時（ISO 8601形式、例: 2026-02-04T00:00:00+09:00）。"
                            "省略時は現在時刻から取得します。"
                        ),
                    },
                    "time_max": {
                        "type": "string",
                        "description": (
                            "取得終了日時（ISO 8601形式）。"
                            "省略時はtime_minから7日後まで取得します。"
                        ),
                    },
                    "max_results_per_calendar": {
                        "type": "integer",
                        "description": "各カレンダーからの最大取得件数（デフォルト: 10）",
                        "default": 10,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """ツールを呼び出す.

    Args:
        name: ツール名
        arguments: ツールの引数

    Returns:
        list[TextContent]: ツールの実行結果

    Raises:
        ValueError: 未知のツール名が指定された場合
    """
    if name == "list_calendars":
        return await handle_list_calendars(arguments)
    elif name == "get_events":
        return await handle_get_events(arguments)
    elif name == "get_event":
        return await handle_get_event(arguments)
    elif name == "create_event":
        return await handle_create_event(arguments)
    elif name == "update_event":
        return await handle_update_event(arguments)
    elif name == "get_events_from_multiple_calendars":
        return await handle_get_events_from_multiple_calendars(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_list_calendars(arguments: dict) -> list[TextContent]:
    """list_calendarsツールのハンドラ.

    Args:
        arguments: ツールの引数（このツールでは未使用）

    Returns:
        list[TextContent]: カレンダー一覧のテキスト
    """
    try:
        # カレンダー一覧を取得
        calendars = await calendar_client.list_calendars()

        # カレンダーが0件の場合
        if not calendars:
            return [
                TextContent(
                    type="text",
                    text="アクセス可能なカレンダーが見つかりませんでした。",
                )
            ]

        # 結果のフォーマット
        result_lines = [f"カレンダー一覧（全{len(calendars)}件）\n"]

        # プライマリカレンダーを先頭に表示
        primary_calendars = [cal for cal in calendars if cal.primary]
        other_calendars = [cal for cal in calendars if not cal.primary]

        # プライマリカレンダー
        if primary_calendars:
            result_lines.append("【プライマリカレンダー】")
            for calendar in primary_calendars:
                result_lines.append(format_calendar_summary(calendar))

        # その他のカレンダー
        if other_calendars:
            if primary_calendars:
                result_lines.append("\n【その他のカレンダー】")
            for calendar in other_calendars:
                result_lines.append(format_calendar_summary(calendar))

        return [TextContent(type="text", text="\n".join(result_lines))]

    except GoogleCalendarMCPError as e:
        logger.error(
            f"Failed to list calendars: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "details": e.details}},
        )
        return [
            TextContent(
                type="text",
                text=f"カレンダー一覧の取得に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in list_calendars")
        return [
            TextContent(
                type="text",
                text=f"カレンダー一覧の取得に失敗しました: {str(e)}",
            )
        ]


async def handle_get_events(arguments: dict) -> list[TextContent]:
    """get_eventsツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 予定一覧のテキスト
    """
    # パラメータの取得
    calendar_id = arguments.get("calendar_id") or config.google_calendar_id
    time_min_str = arguments.get("time_min")
    time_max_str = arguments.get("time_max")
    max_results = arguments.get("max_results", 10)

    try:
        # 日時の解析
        if time_min_str:
            time_min = parse_datetime(time_min_str)
        else:
            # デフォルト: 現在時刻（タイムゾーン付き）
            time_min = datetime.now(timezone.utc)

        if time_max_str:
            time_max = parse_datetime(time_max_str)
        else:
            # デフォルト: time_minから7日後
            time_max = time_min + timedelta(days=7)

        # イベントを取得
        events = await calendar_client.list_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

        # イベントが0件の場合
        if not events:
            return [
                TextContent(
                    type="text",
                    text="指定期間内に予定が見つかりませんでした。",
                )
            ]

        # 今日と今週の判定用
        today = datetime.now().date()
        week_end = today + timedelta(days=7)

        # イベントを今日・今週・それ以降に分類
        today_events = []
        this_week_events = []
        other_events = []

        for event in events:
            event_date = get_event_date(event)
            if event_date == today:
                today_events.append(event)
            elif today < event_date <= week_end:
                this_week_events.append(event)
            else:
                other_events.append(event)

        # 結果のフォーマット
        result_lines = []

        # カレンダー情報を追加（デフォルトカレンダーでない場合）
        if calendar_id != config.google_calendar_id:
            result_lines.append(f"カレンダー: {calendar_id}\n")

        result_lines.append(f"予定一覧（全{len(events)}件）\n")

        # 今日の予定
        if today_events:
            result_lines.append("【今日の予定】")
            for event in today_events:
                result_lines.append(format_event_summary(event))

        # 今週の予定
        if this_week_events:
            result_lines.append("\n【今週の予定】")
            for event in this_week_events:
                result_lines.append(format_event_summary(event))

        # その他の予定
        if other_events:
            result_lines.append("\n【それ以降の予定】")
            for event in other_events:
                result_lines.append(format_event_summary(event))

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 日時の形式が不正です: {str(e)}",
            )
        ]
    except GoogleCalendarMCPError as e:
        logger.error(
            f"Failed to get events: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "details": e.details}},
        )
        return [
            TextContent(
                type="text",
                text=f"予定の取得に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in get_events")
        return [
            TextContent(
                type="text",
                text=f"予定の取得に失敗しました: {str(e)}",
            )
        ]


async def handle_get_event(arguments: dict) -> list[TextContent]:
    """get_eventツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 予定詳細のテキスト
    """
    event_id = arguments.get("event_id")
    calendar_id = arguments.get("calendar_id") or config.google_calendar_id

    if not event_id:
        return [
            TextContent(
                type="text",
                text="エラー: event_idは必須パラメータです。",
            )
        ]

    try:
        # イベント詳細を取得
        event = await calendar_client.get_event(
            event_id=event_id,
            calendar_id=calendar_id,
        )

        # 詳細のフォーマット
        result = format_event_detail(event)

        return [TextContent(type="text", text=result)]

    except GoogleCalendarMCPError as e:
        logger.error(
            f"Failed to get event: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "event_id": event_id}},
        )
        return [
            TextContent(
                type="text",
                text=f"予定の取得に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in get_event")
        return [
            TextContent(
                type="text",
                text=f"予定の取得に失敗しました: {str(e)}",
            )
        ]


async def handle_create_event(arguments: dict) -> list[TextContent]:
    """create_eventツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 作成結果のテキスト
    """
    summary = arguments.get("summary")
    start_time_str = arguments.get("start_time")
    end_time_str = arguments.get("end_time")
    location = arguments.get("location")
    description = arguments.get("description")
    calendar_id = arguments.get("calendar_id") or config.google_calendar_id

    if not summary or not start_time_str or not end_time_str:
        return [
            TextContent(
                type="text",
                text="エラー: summary、start_time、end_timeは必須パラメータです。",
            )
        ]

    try:
        # 日時の解析
        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)

        # イベントオブジェクトの構築
        # Note: IDはサーバー側で自動生成されるため、仮のIDを設定
        event = CalendarEvent(
            id="temp",  # 仮のID（作成時には使用されない）
            summary=summary,
            start=EventDateTime(
                date_time=start_time,
                time_zone=config.google_calendar_timezone,
            ),
            end=EventDateTime(
                date_time=end_time,
                time_zone=config.google_calendar_timezone,
            ),
            location=location,
            description=description,
            status="confirmed",
            html_link="",  # 仮のURL
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        # イベントを作成
        created_event = await calendar_client.create_event(
            event=event,
            calendar_id=calendar_id,
        )

        # 結果のフォーマット
        result_lines = ["予定を作成しました。\n"]

        # カレンダー情報を追加（デフォルトカレンダーでない場合）
        if calendar_id != config.google_calendar_id:
            result_lines.append(f"カレンダー: {calendar_id}")

        result_lines.extend([
            f"タイトル: {created_event.summary}",
            f"開始: {format_event_time(created_event.start)}",
            f"終了: {format_event_time(created_event.end)}",
        ])

        if created_event.location:
            result_lines.append(f"場所: {created_event.location}")

        if created_event.description:
            # 説明が長い場合は省略
            desc_preview = (
                created_event.description[:100] + "..."
                if len(created_event.description) > 100
                else created_event.description
            )
            result_lines.append(f"説明: {desc_preview}")

        result_lines.append(f"\nURL: {created_event.html_link}")
        result_lines.append(f"ID: {created_event.id}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 日時の形式が不正です: {str(e)}",
            )
        ]
    except GoogleCalendarMCPError as e:
        logger.error(
            f"Failed to create event: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "summary": summary}},
        )
        return [
            TextContent(
                type="text",
                text=f"予定の作成に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in create_event")
        return [
            TextContent(
                type="text",
                text=f"予定の作成に失敗しました: {str(e)}",
            )
        ]


async def handle_update_event(arguments: dict) -> list[TextContent]:
    """update_eventツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 更新結果のテキスト
    """
    event_id = arguments.get("event_id")
    summary = arguments.get("summary")
    start_time_str = arguments.get("start_time")
    end_time_str = arguments.get("end_time")
    location = arguments.get("location")
    description = arguments.get("description")
    calendar_id = arguments.get("calendar_id") or config.google_calendar_id

    if not event_id:
        return [
            TextContent(
                type="text",
                text="エラー: event_idは必須パラメータです。",
            )
        ]

    try:
        # 更新データの構築
        updates: dict[str, Any] = {}

        if summary:
            updates["summary"] = summary

        if start_time_str:
            start_time = parse_datetime(start_time_str)
            updates["start"] = {
                "dateTime": start_time.isoformat(),
                "timeZone": config.google_calendar_timezone,
            }

        if end_time_str:
            end_time = parse_datetime(end_time_str)
            updates["end"] = {
                "dateTime": end_time.isoformat(),
                "timeZone": config.google_calendar_timezone,
            }

        if location is not None:  # 空文字列も許容（削除の場合）
            updates["location"] = location

        if description is not None:
            updates["description"] = description

        # 更新内容がない場合
        if not updates:
            return [
                TextContent(
                    type="text",
                    text="エラー: 更新する内容が指定されていません。",
                )
            ]

        # イベントを更新
        updated_event = await calendar_client.update_event(
            event_id=event_id,
            updates=updates,
            calendar_id=calendar_id,
        )

        # 結果のフォーマット
        result_lines = ["予定を更新しました。\n"]

        # カレンダー情報を追加（デフォルトカレンダーでない場合）
        if calendar_id != config.google_calendar_id:
            result_lines.append(f"カレンダー: {calendar_id}")

        result_lines.extend([
            f"タイトル: {updated_event.summary}",
            f"開始: {format_event_time(updated_event.start)}",
            f"終了: {format_event_time(updated_event.end)}",
        ])

        if updated_event.location:
            result_lines.append(f"場所: {updated_event.location}")

        result_lines.append(f"\nURL: {updated_event.html_link}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 日時の形式が不正です: {str(e)}",
            )
        ]
    except GoogleCalendarMCPError as e:
        logger.error(
            f"Failed to update event: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "event_id": event_id}},
        )
        return [
            TextContent(
                type="text",
                text=f"予定の更新に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in update_event")
        return [
            TextContent(
                type="text",
                text=f"予定の更新に失敗しました: {str(e)}",
            )
        ]


async def handle_get_events_from_multiple_calendars(arguments: dict) -> list[TextContent]:
    """get_events_from_multiple_calendarsツールのハンドラ.

    複数のカレンダーから予定を一括取得し、時系列順に表示します。

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 予定一覧のテキスト
    """
    calendar_ids_arg = arguments.get("calendar_ids")
    time_min_str = arguments.get("time_min")
    time_max_str = arguments.get("time_max")
    max_results_per_calendar = arguments.get("max_results_per_calendar", 10)

    try:
        # 日時の解析
        if time_min_str:
            time_min = parse_datetime(time_min_str)
        else:
            # デフォルト: 現在時刻（タイムゾーン付き）
            time_min = datetime.now(timezone.utc)

        if time_max_str:
            time_max = parse_datetime(time_max_str)
        else:
            # デフォルト: time_minから7日後
            time_max = time_min + timedelta(days=7)

        # カレンダーIDリストの取得
        # 省略時はすべてのカレンダーから取得
        if calendar_ids_arg:
            calendar_ids = calendar_ids_arg
            # カレンダー名のマッピングを取得（表示用）
            all_calendars = await calendar_client.list_calendars()
            calendar_name_map = {cal.id: cal.summary for cal in all_calendars}
        else:
            # すべてのカレンダーを取得
            all_calendars = await calendar_client.list_calendars()
            calendar_ids = [cal.id for cal in all_calendars]
            calendar_name_map = {cal.id: cal.summary for cal in all_calendars}

        # カレンダーが0件の場合
        if not calendar_ids:
            return [
                TextContent(
                    type="text",
                    text="アクセス可能なカレンダーが見つかりませんでした。",
                )
            ]

        # 各カレンダーから予定を並行取得
        # エラーが発生しても他のカレンダーは継続して取得する
        async def fetch_events_from_calendar(calendar_id: str) -> tuple[str, list[CalendarEvent], Optional[str]]:
            """カレンダーから予定を取得（エラー処理込み）.

            Args:
                calendar_id: カレンダーID

            Returns:
                tuple[str, list[CalendarEvent], Optional[str]]:
                    (カレンダーID, 予定リスト, エラーメッセージ)
            """
            try:
                events = await calendar_client.list_events(
                    calendar_id=calendar_id,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=max_results_per_calendar,
                )
                return (calendar_id, events, None)
            except GoogleCalendarMCPError as e:
                # エラーが発生しても他のカレンダーは継続
                logger.warning(
                    f"Failed to get events from calendar '{calendar_id}': {e}",
                    extra={"extra_fields": {"calendar_id": calendar_id, "error": str(e)}},
                )
                return (calendar_id, [], f"{e.message}")
            except Exception as e:
                logger.warning(
                    f"Unexpected error getting events from calendar '{calendar_id}': {e}",
                    extra={"extra_fields": {"calendar_id": calendar_id, "error": str(e)}},
                )
                return (calendar_id, [], f"予期しないエラー: {str(e)}")

        # 並行実行
        results = await asyncio.gather(
            *[fetch_events_from_calendar(cal_id) for cal_id in calendar_ids]
        )

        # 結果を集約
        all_events: list[tuple[CalendarEvent, str, str]] = []  # (event, calendar_id, calendar_name)
        error_messages: list[str] = []

        for calendar_id, events, error_msg in results:
            calendar_name = calendar_name_map.get(calendar_id, calendar_id)

            if error_msg:
                # エラーが発生したカレンダーを記録
                error_messages.append(f"⚠️ {calendar_name}: {error_msg}")
            else:
                # 予定にカレンダー情報を付加
                for event in events:
                    all_events.append((event, calendar_id, calendar_name))

        # 予定が0件の場合
        if not all_events:
            result_lines = ["指定期間内に予定が見つかりませんでした。"]
            if error_messages:
                result_lines.append("\n【エラー】")
                result_lines.extend(error_messages)
            return [TextContent(type="text", text="\n".join(result_lines))]

        # 開始日時順にソート
        all_events.sort(key=lambda item: get_event_date(item[0]))

        # 今日と今週の判定用
        today = datetime.now().date()
        week_end = today + timedelta(days=7)

        # イベントを今日・今週・それ以降に分類
        today_events = []
        this_week_events = []
        other_events = []

        for event_tuple in all_events:
            event, calendar_id, calendar_name = event_tuple
            event_date = get_event_date(event)
            if event_date == today:
                today_events.append(event_tuple)
            elif today < event_date <= week_end:
                this_week_events.append(event_tuple)
            else:
                other_events.append(event_tuple)

        # 結果のフォーマット
        result_lines = []

        # サマリー情報
        total_calendars = len(calendar_ids)
        successful_calendars = total_calendars - len(error_messages)
        result_lines.append(
            f"複数カレンダーから予定を取得しました（{successful_calendars}/{total_calendars}カレンダー、全{len(all_events)}件）\n"
        )

        # 今日の予定
        if today_events:
            result_lines.append("【今日の予定】")
            for event, calendar_id, calendar_name in today_events:
                result_lines.append(format_event_with_calendar(event, calendar_name))

        # 今週の予定
        if this_week_events:
            result_lines.append("\n【今週の予定】")
            for event, calendar_id, calendar_name in this_week_events:
                result_lines.append(format_event_with_calendar(event, calendar_name))

        # その他の予定
        if other_events:
            result_lines.append("\n【それ以降の予定】")
            for event, calendar_id, calendar_name in other_events:
                result_lines.append(format_event_with_calendar(event, calendar_name))

        # エラーメッセージを追加
        if error_messages:
            result_lines.append("\n【エラーが発生したカレンダー】")
            result_lines.extend(error_messages)

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 日時の形式が不正です: {str(e)}",
            )
        ]
    except GoogleCalendarMCPError as e:
        logger.error(
            f"Failed to get events from multiple calendars: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "details": e.details}},
        )
        return [
            TextContent(
                type="text",
                text=f"予定の取得に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in get_events_from_multiple_calendars")
        return [
            TextContent(
                type="text",
                text=f"予定の取得に失敗しました: {str(e)}",
            )
        ]


# === ヘルパー関数 ===


def parse_datetime(datetime_str: str) -> datetime:
    """ISO 8601形式の文字列をdatetimeオブジェクトに変換.

    Args:
        datetime_str: ISO 8601形式の日時文字列

    Returns:
        datetime: datetimeオブジェクト

    Raises:
        ValueError: 日時の解析に失敗した場合
    """
    try:
        # ISO 8601形式をパース
        # タイムゾーン情報を含む場合と含まない場合に対応
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return dt
    except ValueError as e:
        raise ValueError(
            f"日時の形式が不正です。ISO 8601形式（例: 2026-02-04T10:00:00+09:00）で指定してください: {datetime_str}"
        ) from e


def get_event_date(event: CalendarEvent) -> datetime.date:
    """イベントの日付を取得.

    Args:
        event: カレンダーイベント

    Returns:
        datetime.date: イベントの日付
    """
    if event.start.date_time:
        return event.start.date_time.date()
    elif event.start.date:
        # 終日イベントの場合
        return datetime.fromisoformat(event.start.date).date()
    else:
        # フォールバック: 今日の日付
        return datetime.now().date()


def format_event_time(event_dt: EventDateTime) -> str:
    """イベント日時を読みやすい形式にフォーマット.

    Args:
        event_dt: イベント日時

    Returns:
        str: フォーマットされた日時文字列
    """
    if event_dt.date_time:
        # 時刻指定あり: YYYY-MM-DD HH:MM形式
        return event_dt.date_time.strftime("%Y-%m-%d %H:%M")
    elif event_dt.date:
        # 終日イベント: YYYY-MM-DD形式
        return event_dt.date
    else:
        return "（日時不明）"


def format_calendar_summary(calendar) -> str:
    """カレンダーの概要をフォーマット.

    Args:
        calendar: カレンダー

    Returns:
        str: フォーマットされたカレンダー概要
    """
    # アクセス権限の日本語表示
    access_role_map = {
        "owner": "オーナー",
        "writer": "編集者",
        "reader": "閲覧者",
        "freeBusyReader": "空き時間情報のみ",
    }
    access_role_ja = access_role_map.get(calendar.access_role, calendar.access_role)

    # プライマリカレンダーの場合は印をつける
    primary_mark = "⭐ " if calendar.primary else ""

    result = [
        f"{primary_mark}📅 {calendar.summary}",
        f"   - ID: {calendar.id}",
        f"   - アクセス権限: {access_role_ja}",
    ]

    if calendar.time_zone:
        result.append(f"   - タイムゾーン: {calendar.time_zone}")

    if calendar.description:
        # 説明が長い場合は省略
        desc_preview = (
            calendar.description[:50] + "..."
            if len(calendar.description) > 50
            else calendar.description
        )
        result.append(f"   - 説明: {desc_preview}")

    return "\n".join(result) + "\n"


def format_event_summary(event: CalendarEvent) -> str:
    """イベントの概要を1行でフォーマット.

    Args:
        event: カレンダーイベント

    Returns:
        str: フォーマットされたイベント概要
    """
    title = event.summary or "（タイトルなし）"
    start_str = format_event_time(event.start)
    end_str = format_event_time(event.end)
    location_str = f" - {event.location}" if event.location else ""

    return (
        f"📅 {title}\n"
        f"   - 時間: {start_str} - {end_str}{location_str}\n"
        f"   - ID: {event.id}\n"
    )


def format_event_detail(event: CalendarEvent) -> str:
    """イベントの詳細情報をフォーマット.

    Args:
        event: カレンダーイベント

    Returns:
        str: フォーマットされたイベント詳細
    """
    lines = [
        f"# {event.summary or '（タイトルなし）'}\n",
        f"- 開始: {format_event_time(event.start)}",
        f"- 終了: {format_event_time(event.end)}",
    ]

    if event.location:
        lines.append(f"- 場所: {event.location}")

    lines.append(f"- ステータス: {event.status.value}")

    if event.description:
        lines.append(f"\n## 説明\n\n{event.description}")

    lines.append(f"\n- URL: {event.html_link}")
    lines.append(f"- ID: {event.id}")

    return "\n".join(lines)


def format_event_with_calendar(event: CalendarEvent, calendar_name: str) -> str:
    """イベントの概要をカレンダー名付きでフォーマット.

    Args:
        event: カレンダーイベント
        calendar_name: カレンダー名

    Returns:
        str: フォーマットされたイベント概要
    """
    title = event.summary or "（タイトルなし）"
    start_str = format_event_time(event.start)
    end_str = format_event_time(event.end)
    location_str = f" - {event.location}" if event.location else ""

    return (
        f"📅 {title} [{calendar_name}]\n"
        f"   - 時間: {start_str} - {end_str}{location_str}\n"
        f"   - ID: {event.id}\n"
    )


async def main() -> None:
    """MCPサーバーのメインエントリーポイント."""
    global config, calendar_client

    # 設定を読み込み
    try:
        config = GoogleCalendarConfig()
        logger.info(
            "Configuration loaded successfully",
            extra={"extra_fields": {"log_level": config.mcp_log_level}},
        )
    except Exception as e:
        logger.error(
            f"Failed to load configuration: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__}},
        )
        raise ConfigurationError(
            message="環境変数の読み込みに失敗しました。.envファイルを確認してください。",
            original_error=e,
        )

    # Google Calendar認証を初期化
    try:
        auth = GoogleCalendarAuth(config)
        logger.info("Google Calendar auth initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar auth: {e}")
        raise

    # Google Calendarクライアントを初期化
    try:
        calendar_client = GoogleCalendarClient(config, auth)
        logger.info("Google Calendar client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar client: {e}")
        raise

    try:
        # MCPサーバーを起動
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server starting...")
            await server.run(read_stream, write_stream, server.create_initialization_options())
    except GoogleCalendarMCPError as e:
        # カスタム例外はログに記録して再発生
        logger.error(
            f"MCP server error: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "details": e.details}},
        )
        raise
    except Exception as e:
        # 予期しない例外もログに記録
        logger.exception("Unexpected error in MCP server")
        raise
    finally:
        # クリーンアップ
        await calendar_client.close()
        logger.info("MCP server stopped")


if __name__ == "__main__":
    asyncio.run(main())
