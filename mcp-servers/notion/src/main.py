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
                            "Not started",
                            "In Progress",
                            "Completed",
                            "Blocked",
                            "Cancelled",
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
                        "description": "タスクのステータス（デフォルト: Not started）",
                        "enum": [
                            "Not started",
                            "In Progress",
                            "Completed",
                            "Blocked",
                            "Cancelled",
                        ],
                        "default": "Not started",
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
    status_str = arguments.get("status", "Not started")
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
