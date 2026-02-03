"""MCP Server main entry point.

このモジュールは、Fast MCPを使用してMCPサーバーを実装し、
Notion連携のツールを公開します。
"""

import asyncio
import logging
import os
from datetime import date

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .cache import TaskCache
from .config import NotionConfig
from .exceptions import ConfigurationError, NotionMCPError
from .logger import setup_logger
from .models import TaskPriority, TaskStatus
from .notion_client import NotionClient

# ロギング設定（環境変数で制御）
log_level = os.getenv("MCP_LOG_LEVEL", "INFO")
use_json_logs = os.getenv("MCP_LOG_JSON", "false").lower() == "true"

logger = setup_logger(
    name="hisho-notion-mcp",
    level=log_level,
    use_json=use_json_logs,
)

# グローバル変数
config: NotionConfig
notion_client: NotionClient
task_cache: TaskCache
server = Server("hisho-notion-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """利用可能なツール一覧を返す.

    Returns:
        list[Tool]: ツールのリスト
    """
    return [
        Tool(
            name="get_tasks",
            description=(
                "Notionデータベースから未完了のタスク一覧を取得します。"
                "タスクは優先度と期限順にソートされます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "include_completed": {
                        "type": "boolean",
                        "description": "完了済みタスクを含めるか（デフォルト: false）",
                        "default": False,
                    }
                },
            },
        ),
        Tool(
            name="update_task_status",
            description=(
                "Notionのタスクのステータスを更新します。"
                "タスクを完了にしたり、進行中にしたりできます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "更新するタスクのページID",
                    },
                    "status": {
                        "type": "string",
                        "description": "新しいステータス",
                        "enum": [
                            "未着手",
                            "今日やる",
                            "対応中",
                            "バックログ",
                            "完了 🙌",
                            "キャンセル",
                        ],
                    },
                },
                "required": ["page_id", "status"],
            },
        ),
        Tool(
            name="create_task",
            description=(
                "Notionデータベースに新しいタスクを作成します。"
                "タイトル、ステータス、優先度、期限、タグを設定できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "タスクのタイトル",
                    },
                    "status": {
                        "type": "string",
                        "description": "タスクのステータス（デフォルト: 未着手）",
                        "enum": [
                            "未着手",
                            "今日やる",
                            "対応中",
                            "バックログ",
                            "完了 🙌",
                            "キャンセル",
                        ],
                        "default": "未着手",
                    },
                    "priority": {
                        "type": "string",
                        "description": "タスクの優先度",
                        "enum": ["High", "Medium", "Low"],
                    },
                    "due_date": {
                        "type": "string",
                        "description": "期限（ISO 8601形式: YYYY-MM-DD）",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "タグのリスト",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="create_memo",
            description=(
                "Notionのメモデータベースに新しいメモを作成します。"
                "会議メモ、アイデア、日記などを記録できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "メモのタイトル",
                    },
                    "content": {
                        "type": "string",
                        "description": "メモの内容（本文）",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "タグのリスト",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="update_task",
            description=(
                "Notionのタスクの内容を更新します。"
                "タイトル、ステータス、優先度、期限、タグを変更できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "更新するタスクのページID",
                    },
                    "title": {
                        "type": "string",
                        "description": "新しいタイトル（変更する場合のみ）",
                    },
                    "status": {
                        "type": "string",
                        "description": "新しいステータス（変更する場合のみ）",
                        "enum": [
                            "未着手",
                            "今日やる",
                            "対応中",
                            "バックログ",
                            "完了 🙌",
                            "キャンセル",
                        ],
                    },
                    "priority": {
                        "type": "string",
                        "description": "新しい優先度（変更する場合のみ）",
                        "enum": ["High", "Medium", "Low"],
                    },
                    "due_date": {
                        "type": "string",
                        "description": "新しい期限（ISO 8601形式: YYYY-MM-DD）（変更する場合のみ）",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新しいタグのリスト（変更する場合のみ）",
                    },
                },
                "required": ["page_id"],
            },
        ),
        Tool(
            name="update_memo",
            description=(
                "Notionのメモの内容を更新します。"
                "タイトル、タグの変更や、内容（本文）の追記ができます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "更新するメモのページID",
                    },
                    "title": {
                        "type": "string",
                        "description": "新しいタイトル（変更する場合のみ）",
                    },
                    "content": {
                        "type": "string",
                        "description": "追記する内容（本文）（追記する場合のみ）",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新しいタグのリスト（変更する場合のみ）",
                    },
                },
                "required": ["page_id"],
            },
        ),
        Tool(
            name="list_memos",
            description=(
                "Notionのメモデータベースからメモ一覧を取得します。"
                "作成日時順の降順（新しい順）で返されます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="read_task",
            description=(
                "Notionのタスクの詳細情報を取得します。"
                "タイトル、ステータス、期限などのプロパティに加え、"
                "タスクの本文（ブロック）も取得します。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "取得するタスクのページID",
                    }
                },
                "required": ["page_id"],
            },
        ),
        Tool(
            name="read_memo",
            description=(
                "Notionのメモの詳細情報を取得します。"
                "タイトル、タグなどのプロパティに加え、"
                "メモの本文（ブロック）も取得します。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "取得するメモのページID",
                    }
                },
                "required": ["page_id"],
            },
        ),
        Tool(
            name="search_tasks",
            description=(
                "Notionのタスクを検索します。"
                "キーワード（タイトル）やタグ、ステータスで絞り込み可能です。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード（タイトルに含まれる文字列）",
                    },
                    "status": {
                        "type": "string",
                        "description": "ステータスで絞り込み",
                        "enum": [
                            "未着手",
                            "今日やる",
                            "対応中",
                            "バックログ",
                            "完了 🙌",
                            "キャンセル",
                        ],
                    },
                    "tag": {
                        "type": "string",
                        "description": "タグで絞り込み",
                    },
                },
            },
        ),
        Tool(
            name="search_memos",
            description=(
                "Notionのメモを検索します。"
                "キーワード（タイトル）やタグで絞り込み可能です。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード（タイトルに含まれる文字列）",
                    },
                    "tag": {
                        "type": "string",
                        "description": "タグで絞り込み",
                    },
                },
            },
        ),
        Tool(
            name="check_subtask_item",
            description=(
                "タスクやメモ内のサブタスク（チェックボックス/TODOリスト）の状態を更新します。"
                "完了（チェックあり）または未完了（チェックなし）に設定できます。"
                "read_taskなどで取得したBlock IDを使用してください。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "block_id": {
                        "type": "string",
                        "description": "更新するTODOブロックのID",
                    },
                    "checked": {
                        "type": "boolean",
                        "description": "チェック状態（true: 完了, false: 未完了）",
                    },
                },
                "required": ["block_id", "checked"],
            },
        ),
        Tool(
            name="add_comment",
            description=(
                "タスクやメモのページにコメントを追加します。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "コメントを追加するページID",
                    },
                    "content": {
                        "type": "string",
                        "description": "コメントの内容",
                    },
                },
                "required": ["page_id", "content"],
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
    if name == "get_tasks":
        return await handle_get_tasks(arguments)
    elif name == "update_task_status":
        return await handle_update_task_status(arguments)
    elif name == "create_task":
        return await handle_create_task(arguments)
    elif name == "create_memo":
        return await handle_create_memo(arguments)
    elif name == "update_task":
        return await handle_update_task(arguments)
    elif name == "update_memo":
        return await handle_update_memo(arguments)
    elif name == "list_memos":
        return await handle_list_memos(arguments)
    elif name == "read_task":
        return await handle_read_task(arguments)
    elif name == "read_memo":
        return await handle_read_memo(arguments)
    elif name == "search_tasks":
        return await handle_search_tasks(arguments)
    elif name == "search_memos":
        return await handle_search_memos(arguments)
    elif name == "check_subtask_item":
        return await handle_check_subtask_item(arguments)
    elif name == "add_comment":
        return await handle_add_comment(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_get_tasks(arguments: dict) -> list[TextContent]:
    """get_tasksツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: タスク一覧のテキスト
    """
    include_completed = arguments.get("include_completed", False)

    try:
        # キャッシュから取得を試みる
        database_id = config.notion_task_database_id
        cached_tasks = await task_cache.get_tasks(database_id, include_completed)

        if cached_tasks is not None:
            logger.debug("Using cached tasks")
            tasks = cached_tasks
        else:
            # キャッシュにない場合はAPIから取得
            tasks = await notion_client.get_tasks(include_completed=include_completed)
            # キャッシュに保存
            await task_cache.set_tasks(database_id, include_completed, tasks)

        # タスクが0件の場合
        if not tasks:
            return [
                TextContent(
                    type="text",
                    text="タスクが見つかりませんでした。新しいタスクを追加してください。",
                )
            ]

        # タスクを整形して返す
        result_lines = [f"タスク一覧（全{len(tasks)}件）\n"]

        # 期限が今日のタスク
        today = date.today()
        today_tasks = [t for t in tasks if t.due_date == today]
        if today_tasks:
            result_lines.append("【期限が今日のタスク】")
            for task in today_tasks:
                priority_str = f"（優先度: {task.priority.value}）" if task.priority else ""
                tags_str = f" #{' #'.join(task.tags)}" if task.tags else ""
                result_lines.append(
                    f"⚠️ {task.title}{priority_str}\n"
                    f"   - ステータス: {task.status.value}\n"
                    f"   - URL: {task.url}{tags_str}\n"
                )

        # 期限が過ぎているタスク
        overdue_tasks = [t for t in tasks if t.due_date and t.due_date < today]
        if overdue_tasks:
            result_lines.append("\n【期限超過のタスク】")
            for task in overdue_tasks:
                priority_str = f"（優先度: {task.priority.value}）" if task.priority else ""
                tags_str = f" #{' #'.join(task.tags)}" if task.tags else ""
                days_overdue = (today - task.due_date).days
                result_lines.append(
                    f"🔴 {task.title}{priority_str}\n"
                    f"   - 期限: {task.due_date} ({days_overdue}日超過)\n"
                    f"   - ステータス: {task.status.value}\n"
                    f"   - URL: {task.url}{tags_str}\n"
                )

        # 期限が近いタスク（3日以内）
        near_due_tasks = [
            t
            for t in tasks
            if t.due_date and today < t.due_date <= date.fromordinal(today.toordinal() + 3)
        ]
        if near_due_tasks:
            result_lines.append("\n【期限が近いタスク（3日以内）】")
            for task in near_due_tasks:
                priority_str = f"（優先度: {task.priority.value}）" if task.priority else ""
                tags_str = f" #{' #'.join(task.tags)}" if task.tags else ""
                days_until = (task.due_date - today).days
                result_lines.append(
                    f"{task.title}{priority_str}\n"
                    f"   - 期限: {task.due_date} (あと{days_until}日)\n"
                    f"   - ステータス: {task.status.value}\n"
                    f"   - URL: {task.url}{tags_str}\n"
                )

        # その他のタスク
        other_tasks = [
            t
            for t in tasks
            if not t.due_date
            or t.due_date > date.fromordinal(today.toordinal() + 3)
        ]
        if other_tasks:
            result_lines.append("\n【その他のタスク】")
            for task in other_tasks[:10]:  # 最大10件まで表示
                priority_str = f"（優先度: {task.priority.value}）" if task.priority else ""
                due_str = f" - 期限: {task.due_date}" if task.due_date else ""
                tags_str = f" #{' #'.join(task.tags)}" if task.tags else ""
                result_lines.append(
                    f"{task.title}{priority_str}\n"
                    f"   - ステータス: {task.status.value}{due_str}\n"
                    f"   - URL: {task.url}{tags_str}\n"
                )
            if len(other_tasks) > 10:
                result_lines.append(f"\n...他 {len(other_tasks) - 10}件のタスク")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except NotionMCPError as e:
        logger.error(
            f"Failed to get tasks: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "details": e.details}},
        )
        return [
            TextContent(
                type="text",
                text=f"タスクの取得に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in get_tasks")
        return [
            TextContent(
                type="text",
                text=f"タスクの取得に失敗しました: {str(e)}",
            )
        ]


async def handle_update_task_status(arguments: dict) -> list[TextContent]:
    """update_task_statusツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 更新結果のテキスト
    """
    page_id = arguments.get("page_id")
    status_str = arguments.get("status")

    if not page_id or not status_str:
        return [
            TextContent(
                type="text",
                text="エラー: page_idとstatusは必須パラメータです。",
            )
        ]

    try:
        # ステータス文字列をTaskStatus enumに変換
        status = TaskStatus(status_str)

        # タスクのステータスを更新
        updated_task = await notion_client.update_task_status(page_id, status)

        # キャッシュを無効化
        await task_cache.invalidate_database(config.notion_task_database_id)

        return [
            TextContent(
                type="text",
                text=(
                    f"タスクのステータスを更新しました。\n\n"
                    f"タイトル: {updated_task.title}\n"
                    f"新しいステータス: {updated_task.status.value}\n"
                    f"URL: {updated_task.url}"
                ),
            )
        ]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 無効なステータス値です: {status_str}",
            )
        ]
    except NotionMCPError as e:
        logger.error(
            f"Failed to update task status: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "page_id": page_id}},
        )
        return [
            TextContent(
                type="text",
                text=f"タスクのステータス更新に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in update_task_status")
        return [
            TextContent(
                type="text",
                text=f"タスクのステータス更新に失敗しました: {str(e)}",
            )
        ]


async def handle_create_task(arguments: dict) -> list[TextContent]:
    """create_taskツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 作成結果のテキスト
    """
    title = arguments.get("title")
    status_str = arguments.get("status", "未着手")
    priority_str = arguments.get("priority")
    due_date = arguments.get("due_date")
    tags = arguments.get("tags")

    if not title:
        return [
            TextContent(
                type="text",
                text="エラー: titleは必須パラメータです。",
            )
        ]

    try:
        # ステータスと優先度をenumに変換
        status = TaskStatus(status_str)
        priority = TaskPriority(priority_str) if priority_str else None

        # タスクを作成
        new_task = await notion_client.create_task(
            title=title,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags,
        )

        # キャッシュを無効化
        await task_cache.invalidate_database(config.notion_task_database_id)

        # 結果のフォーマット
        result_lines = [
            "新しいタスクを作成しました。\n",
            f"タイトル: {new_task.title}",
            f"ステータス: {new_task.status.value}",
        ]

        if new_task.priority:
            result_lines.append(f"優先度: {new_task.priority.value}")

        if new_task.due_date:
            result_lines.append(f"期限: {new_task.due_date}")

        if new_task.tags:
            tags_str = ", ".join(new_task.tags)
            result_lines.append(f"タグ: {tags_str}")

        result_lines.append(f"\nURL: {new_task.url}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 無効なパラメータ値です: {str(e)}",
            )
        ]
    except NotionMCPError as e:
        logger.error(
            f"Failed to create task: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "title": title}},
        )
        return [
            TextContent(
                type="text",
                text=f"タスクの作成に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in create_task")
        return [
            TextContent(
                type="text",
                text=f"タスクの作成に失敗しました: {str(e)}",
            )
        ]


async def handle_create_memo(arguments: dict) -> list[TextContent]:
    """create_memoツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 作成結果のテキスト
    """
    title = arguments.get("title")
    content = arguments.get("content")
    tags = arguments.get("tags")

    if not title:
        return [
            TextContent(
                type="text",
                text="エラー: titleは必須パラメータです。",
            )
        ]

    try:
        # メモを作成
        memo_page = await notion_client.create_memo(
            title=title,
            content=content,
            tags=tags,
        )

        # 結果のフォーマット
        result_lines = [
            "新しいメモを作成しました。\n",
            f"タイトル: {title}",
        ]

        if content:
            # 内容が長い場合は省略
            content_preview = (
                content[:100] + "..." if len(content) > 100 else content
            )
            result_lines.append(f"内容: {content_preview}")

        if tags:
            tags_str = ", ".join(tags)
            result_lines.append(f"タグ: {tags_str}")

        result_lines.append(f"\nURL: {memo_page['url']}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except NotionMCPError as e:
        logger.error(
            f"Failed to create memo: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "title": title}},
        )
        return [
            TextContent(
                type="text",
                text=f"メモの作成に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in create_memo")
        return [
            TextContent(
                type="text",
                text=f"メモの作成に失敗しました: {str(e)}",
            )
        ]


async def handle_update_task(arguments: dict) -> list[TextContent]:
    """update_taskツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 更新結果のテキスト
    """
    page_id = arguments.get("page_id")
    title = arguments.get("title")
    status_str = arguments.get("status")
    priority_str = arguments.get("priority")
    due_date = arguments.get("due_date")
    tags = arguments.get("tags")

    if not page_id:
        return [
            TextContent(
                type="text",
                text="エラー: page_idは必須パラメータです。",
            )
        ]

    try:
        # ステータスと優先度をenumに変換
        status = TaskStatus(status_str) if status_str else None
        priority = TaskPriority(priority_str) if priority_str else None

        # タスクを更新
        updated_task = await notion_client.update_task(
            page_id=page_id,
            title=title,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags,
        )

        # キャッシュを無効化
        await task_cache.invalidate_database(config.notion_task_database_id)

        # 結果のフォーマット
        result_lines = [
            "タスクを更新しました。\n",
            f"タイトル: {updated_task.title}",
            f"ステータス: {updated_task.status.value}",
        ]

        if updated_task.priority:
            result_lines.append(f"優先度: {updated_task.priority.value}")

        if updated_task.due_date:
            result_lines.append(f"期限: {updated_task.due_date}")

        if updated_task.tags:
            tags_str = ", ".join(updated_task.tags)
            result_lines.append(f"タグ: {tags_str}")

        result_lines.append(f"\nURL: {updated_task.url}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=f"エラー: 無効なパラメータ値です: {str(e)}",
            )
        ]
    except NotionMCPError as e:
        logger.error(
            f"Failed to update task: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "page_id": page_id}},
        )
        return [
            TextContent(
                type="text",
                text=f"タスクの更新に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in update_task")
        return [
            TextContent(
                type="text",
                text=f"タスクの更新に失敗しました: {str(e)}",
            )
        ]


async def handle_update_memo(arguments: dict) -> list[TextContent]:
    """update_memoツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: 更新結果のテキスト
    """
    page_id = arguments.get("page_id")
    title = arguments.get("title")
    content = arguments.get("content")
    tags = arguments.get("tags")

    if not page_id:
        return [
            TextContent(
                type="text",
                text="エラー: page_idは必須パラメータです。",
            )
        ]

    try:
        # メモを更新
        await notion_client.update_memo(
            page_id=page_id,
            title=title,
            tags=tags,
            content=content,
        )

        # 結果のフォーマット
        result_lines = ["メモを更新しました。\n"]

        if title:
            result_lines.append(f"新しいタイトル: {title}")

        if content:
            # 内容が長い場合は省略
            content_preview = (
                content[:100] + "..." if len(content) > 100 else content
            )
            result_lines.append(f"追記した内容: {content_preview}")

        if tags:
            tags_str = ", ".join(tags)
            result_lines.append(f"新しいタグ: {tags_str}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except NotionMCPError as e:
        logger.error(
            f"Failed to update memo: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__, "page_id": page_id}},
        )
        return [
            TextContent(
                type="text",
                text=f"メモの更新に失敗しました: {e.message}",
            )
        ]
    except Exception as e:
        logger.exception("Unexpected error in update_memo")
        return [
            TextContent(
                type="text",
                text=f"メモの更新に失敗しました: {str(e)}",
            )
        ]

async def handle_list_memos(arguments: dict) -> list[TextContent]:
    """list_memosツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: メモ一覧のテキスト
    """
    try:
        memos = await notion_client.get_memos()

        if not memos:
            return [
                TextContent(
                    type="text",
                    text="メモが見つかりませんでした。",
                )
            ]

        result_lines = [f"メモ一覧（全{len(memos)}件）\n"]

        for memo in memos:
            tags_str = f" #{' #'.join(memo.tags)}" if memo.tags else ""
            date_str = memo.created_time.strftime("%Y-%m-%d %H:%M")
            result_lines.append(
                f"📝 {memo.title}\n"
                f"   - 作成日: {date_str}\n"
                f"   - タグ: {tags_str}\n"
                f"   - URL: {memo.url}\n"
                f"   - ID: {memo.id}\n"
            )

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        logger.exception("Unexpected error in list_memos")
        return [
            TextContent(
                type="text",
                text=f"メモ一覧の取得に失敗しました: {str(e)}",
            )
        ]


async def handle_read_task(arguments: dict) -> list[TextContent]:
    """read_taskツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: タスク詳細のテキスト
    """
    page_id = arguments.get("page_id")
    if not page_id:
        return [TextContent(type="text", text="エラー: page_idは必須です")]

    try:
        # タスク情報の取得
        task = await notion_client.get_task(page_id)
        
        # 本文（ブロック）の取得
        blocks = await notion_client.get_block_children(page_id)
        content_text = notion_client.blocks_to_text(blocks)

        priority_str = f"（優先度: {task.priority.value}）" if task.priority else ""
        due_str = f"期限: {task.due_date}" if task.due_date else "期限なし"
        tags_str = f"#{' #'.join(task.tags)}" if task.tags else "なし"
        
        result = (
            f"# {task.title} {priority_str}\n\n"
            f"- ステータス: {task.status.value}\n"
            f"- {due_str}\n"
            f"- タグ: {tags_str}\n"
            f"- URL: {task.url}\n\n"
            f"## 内容\n\n"
            f"{content_text}"
        )

        return [TextContent(type="text", text=result)]

    except NotionMCPError as e:
        return [TextContent(type="text", text=f"タスクの取得に失敗しました: {e.message}")]
    except Exception as e:
        logger.exception("Unexpected error in read_task")
        return [TextContent(type="text", text=f"タスクの取得に失敗しました: {str(e)}")]


async def handle_read_memo(arguments: dict) -> list[TextContent]:
    """read_memoツールのハンドラ.

    Args:
        arguments: ツールの引数

    Returns:
        list[TextContent]: メモ詳細のテキスト
    """
    page_id = arguments.get("page_id")
    if not page_id:
        return [TextContent(type="text", text="エラー: page_idは必須です")]

    try:
        # メモ情報の取得
        memo = await notion_client.get_memo(page_id)
        
        # 本文（ブロック）の取得
        blocks = await notion_client.get_block_children(page_id)
        content_text = notion_client.blocks_to_text(blocks)

        tags_str = f"#{' #'.join(memo.tags)}" if memo.tags else "なし"
        date_str = memo.created_time.strftime("%Y-%m-%d %H:%M")
        
        result = (
            f"# {memo.title}\n\n"
            f"- 作成日: {date_str}\n"
            f"- タグ: {tags_str}\n"
            f"- URL: {memo.url}\n\n"
            f"## 内容\n\n"
            f"{content_text}"
        )

        return [TextContent(type="text", text=result)]

    except NotionMCPError as e:
        return [TextContent(type="text", text=f"メモの取得に失敗しました: {e.message}")]
    except Exception as e:
        logger.exception("Unexpected error in read_memo")
        return [TextContent(type="text", text=f"メモの取得に失敗しました: {str(e)}")]


async def handle_search_tasks(arguments: dict) -> list[TextContent]:
    """search_tasksツールのハンドラ."""
    query = arguments.get("query")
    status = arguments.get("status")
    tag = arguments.get("tag")

    try:
        tasks = await notion_client.search_tasks(query=query, status=status, tag=tag)
        
        if not tasks:
            return [TextContent(type="text", text="条件に一致するタスクは見つかりませんでした。")]

        result_lines = [f"検索結果（{len(tasks)}件）\n"]
        for task in tasks:
            priority_str = f"（優先度: {task.priority.value}）" if task.priority else ""
            tags_str = f" #{' #'.join(task.tags)}" if task.tags else ""
            result_lines.append(
                f"{task.title}{priority_str}\n"
                f"   - ステータス: {task.status.value}\n"
                f"   - URL: {task.url}{tags_str}\n"
                f"   - ID: {task.id}\n"
            )
        
        return [TextContent(type="text", text="\n".join(result_lines))]
    except Exception as e:
        logger.exception("Unexpected error in search_tasks")
        return [TextContent(type="text", text=f"タスクの検索に失敗しました: {str(e)}")]


async def handle_search_memos(arguments: dict) -> list[TextContent]:
    """search_memosツールのハンドラ."""
    query = arguments.get("query")
    tag = arguments.get("tag")

    try:
        memos = await notion_client.search_memos(query=query, tag=tag)
        
        if not memos:
            return [TextContent(type="text", text="条件に一致するメモは見つかりませんでした。")]

        result_lines = [f"検索結果（{len(memos)}件）\n"]
        for memo in memos:
            tags_str = f" #{' #'.join(memo.tags)}" if memo.tags else ""
            date_str = memo.created_time.strftime("%Y-%m-%d")
            result_lines.append(
                f"📝 {memo.title} ({date_str})\n"
                f"   - URL: {memo.url}{tags_str}\n"
                f"   - ID: {memo.id}\n"
            )
        
        return [TextContent(type="text", text="\n".join(result_lines))]
    except Exception as e:
        logger.exception("Unexpected error in search_memos")
        return [TextContent(type="text", text=f"メモの検索に失敗しました: {str(e)}")]


async def handle_check_subtask_item(arguments: dict) -> list[TextContent]:
    """check_subtask_itemツールのハンドラ."""
    block_id = arguments.get("block_id")
    checked = arguments.get("checked")

    if not block_id:
        return [TextContent(type="text", text="エラー: block_idは必須です")]
    if checked is None:
        return [TextContent(type="text", text="エラー: checkedは必須です")]

    try:
        await notion_client.update_block(
            block_id, 
            "to_do", 
            {"checked": checked}
        )
        status_msg = "完了" if checked else "未完了"
        return [TextContent(type="text", text=f"サブタスク（TODO）を{status_msg}に更新しました。")]
    except Exception as e:
        logger.exception("Unexpected error in check_subtask_item")
        return [TextContent(type="text", text=f"サブタスクの更新に失敗しました: {str(e)}")]


async def handle_add_comment(arguments: dict) -> list[TextContent]:
    """add_commentツールのハンドラ."""
    page_id = arguments.get("page_id")
    content = arguments.get("content")

    if not page_id or not content:
        return [TextContent(type="text", text="エラー: page_idとcontentは必須です")]

    try:
        await notion_client.add_comment_to_page(page_id, content)
        return [TextContent(type="text", text="コメントを追加しました。")]
    except Exception as e:
        logger.exception("Unexpected error in add_comment")
        return [TextContent(type="text", text=f"コメントの追加に失敗しました: {str(e)}")]


async def main() -> None:
    """MCPサーバーのメインエントリーポイント."""
    global config, notion_client, task_cache

    # 設定を読み込み
    try:
        config = NotionConfig()
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

    # Notionクライアントを初期化
    try:
        notion_client = NotionClient(config)
        logger.info("Notion client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Notion client: {e}")
        raise

    # タスクキャッシュを初期化
    task_cache = TaskCache(ttl_seconds=30.0)
    logger.info("Task cache initialized")

    try:
        # MCPサーバーを起動
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server starting...")
            await server.run(read_stream, write_stream, server.create_initialization_options())
    except NotionMCPError as e:
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
        await notion_client.close()
        logger.info("MCP server stopped")


if __name__ == "__main__":
    asyncio.run(main())
