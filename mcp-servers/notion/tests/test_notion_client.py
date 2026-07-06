"""Tests for notion_client module.

NotionClientのAPIクライアント機能をモックを使用してテストします。
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import NotionConfig
from src.exceptions import (
    DataParsingError,
    NotionAPIError,
    NotionValidationError,
)
from src.models import NotionPage, Task, TaskPriority, TaskStatus
from src.notion_client import NotionClient
from src.rate_limiter import RateLimiter


@pytest.fixture
def mock_notion_page() -> dict:
    """モックのNotionページレスポンスを返す.

    Returns:
        dict: Notion APIのページレスポンス
    """
    return {
        "object": "page",
        "id": "test-page-id-123",
        "created_time": "2025-01-15T10:00:00.000Z",
        "last_edited_time": "2025-02-03T10:30:00.000Z",
        "archived": False,
        "properties": {
            "Title": {
                "id": "title",
                "type": "title",
                "title": [{"type": "text", "text": {"content": "テストタスク"}}],
            },
            "Status": {
                "id": "status",
                "type": "status",
                "status": {"name": "対応中", "color": "blue"},  # 日本語ステータス
            },
            "Priority": {
                "id": "priority",
                "type": "select",
                "select": {"name": "High", "color": "red"},
            },
            "Due Date": {
                "id": "due",
                "type": "date",
                "date": {"start": "2025-02-05", "end": None, "time_zone": None},
            },
            "Tags": {
                "id": "tags",
                "type": "multi_select",
                "multi_select": [{"name": "urgent"}, {"name": "important"}],
            },
        },
        "url": "https://www.notion.so/test-page-id-123",
    }


@pytest.fixture
def mock_database_query_response(mock_notion_page: dict) -> dict:
    """モックのデータベースクエリレスポンスを返す.

    Args:
        mock_notion_page: モックのNotionページ

    Returns:
        dict: Notion APIのデータベースクエリレスポンス
    """
    return {
        "object": "list",
        "results": [mock_notion_page],
        "next_cursor": None,
        "has_more": False,
    }


@pytest.fixture
def mock_database_schema() -> dict:
    """モックのデータベーススキーマ（retrieve_database相当）を返す.

    実際のNotionデータベースを模し、ステータスの選択肢に「キャンセル」を
    含めない構成としている（get_tasksが実在する選択肢のみを除外条件に
    含めることを検証するため）。

    Returns:
        dict: Notion APIのデータベースオブジェクト
    """
    return {
        "object": "database",
        "id": "test-database-id",
        "properties": {
            "Status": {
                "id": "status",
                "type": "status",
                "status": {
                    "options": [
                        {"name": "未着手", "color": "default"},
                        {"name": "対応中", "color": "blue"},
                        {"name": "完了 🙌", "color": "green"},
                    ]
                },
            }
        },
    }


class TestNotionClient:
    """NotionClientクラスのテスト."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config: NotionConfig) -> None:
        """NotionClientが正しく初期化されることを確認."""
        client = NotionClient(mock_config)
        assert client.config == mock_config
        assert client.rate_limiter is not None
        await client.close()

    @pytest.mark.asyncio
    async def test_custom_rate_limiter(self, mock_config: NotionConfig) -> None:
        """カスタムレート制限を使用できることを確認."""
        custom_limiter = RateLimiter(tokens_per_second=5.0, capacity=20)
        client = NotionClient(mock_config, rate_limiter=custom_limiter)
        assert client.rate_limiter == custom_limiter
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config: NotionConfig) -> None:
        """コンテキストマネージャーとして使用できることを確認."""
        async with NotionClient(mock_config) as client:
            assert client is not None
        # コンテキスト終了後はクローズされている（明示的に確認はしない）

    @pytest.mark.asyncio
    async def test_query_database_success(
        self, mock_config: NotionConfig, mock_database_query_response: dict
    ) -> None:
        """データベースクエリが成功することを確認."""
        with patch("httpx.AsyncClient.request") as mock_request:
            # モックレスポンスを設定
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_database_query_response
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                pages = await client.query_database()

                # 結果を検証
                assert len(pages) == 1
                assert isinstance(pages[0], NotionPage)
                assert pages[0].id == "test-page-id-123"

    @pytest.mark.asyncio
    async def test_query_database_with_pagination(self, mock_config: NotionConfig) -> None:
        """ページネーションが正しく動作することを確認."""
        # 2ページのレスポンスを準備
        response_page1 = {
            "object": "list",
            "results": [
                {
                    "object": "page",
                    "id": "page-1",
                    "created_time": "2025-01-15T10:00:00.000Z",
                    "last_edited_time": "2025-02-03T10:30:00.000Z",
                    "archived": False,
                    "properties": {},
                    "url": "https://www.notion.so/page-1",
                }
            ],
            "next_cursor": "cursor-123",
            "has_more": True,
        }
        response_page2 = {
            "object": "list",
            "results": [
                {
                    "object": "page",
                    "id": "page-2",
                    "created_time": "2025-01-16T10:00:00.000Z",
                    "last_edited_time": "2025-02-03T10:30:00.000Z",
                    "archived": False,
                    "properties": {},
                    "url": "https://www.notion.so/page-2",
                }
            ],
            "next_cursor": None,
            "has_more": False,
        }

        with patch("httpx.AsyncClient.request") as mock_request:
            # 1回目と2回目で異なるレスポンスを返す
            mock_response1 = MagicMock()
            mock_response1.status_code = 200
            mock_response1.json.return_value = response_page1

            mock_response2 = MagicMock()
            mock_response2.status_code = 200
            mock_response2.json.return_value = response_page2

            mock_request.side_effect = [mock_response1, mock_response2]

            async with NotionClient(mock_config) as client:
                pages = await client.query_database()

                # 2ページ分の結果が取得されていることを確認
                assert len(pages) == 2
                assert pages[0].id == "page-1"
                assert pages[1].id == "page-2"

    @pytest.mark.asyncio
    async def test_parse_task_success(
        self, mock_config: NotionConfig, mock_notion_page: dict
    ) -> None:
        """Notionページが正しくTaskモデルに変換されることを確認."""
        async with NotionClient(mock_config) as client:
            page = NotionPage(**mock_notion_page)
            task = client._parse_task(page)

            # 結果を検証
            assert task.id == "test-page-id-123"
            assert task.title == "テストタスク"
            assert task.status == TaskStatus.IN_PROGRESS
            assert task.priority == TaskPriority.HIGH
            assert task.due_date.isoformat() == "2025-02-05"
            assert "urgent" in task.tags
            assert "important" in task.tags
            assert task.url == "https://www.notion.so/test-page-id-123"

    @pytest.mark.asyncio
    async def test_parse_task_missing_title(self, mock_config: NotionConfig) -> None:
        """タイトルが欠けている場合のエラーハンドリングを確認."""
        page_data = {
            "object": "page",
            "id": "test-page-id",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-02-03T10:30:00.000Z",
            "archived": False,
            "properties": {},  # タイトルなし
            "url": "https://www.notion.so/test-page-id",
        }

        async with NotionClient(mock_config) as client:
            page = NotionPage(**page_data)
            with pytest.raises(DataParsingError):
                client._parse_task(page)

    @pytest.mark.asyncio
    async def test_handle_error_response_json(self, mock_config: NotionConfig) -> None:
        """JSONエラーレスポンスが正しく処理されることを確認."""
        async with NotionClient(mock_config) as client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "object": "error",
                "status": 400,
                "code": "validation_error",
                "message": "Invalid request",
            }

            with pytest.raises(NotionValidationError) as exc_info:
                client._handle_error_response(mock_response)

            assert exc_info.value.status_code == 400
            assert "Invalid request" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_handle_error_response_non_json(self, mock_config: NotionConfig) -> None:
        """JSON以外のエラーレスポンスが正しく処理されることを確認."""
        async with NotionClient(mock_config) as client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.side_effect = ValueError("Not JSON")
            mock_response.text = "Internal Server Error"

            with pytest.raises(DataParsingError) as exc_info:
                client._handle_error_response(mock_response)

            assert exc_info.value.details["status_code"] == 500

    @pytest.mark.asyncio
    async def test_get_tasks_success(
        self, mock_config: NotionConfig, mock_database_query_response: dict
    ) -> None:
        """タスク一覧の取得が成功することを確認."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_database_query_response
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                tasks = await client.get_tasks()

                # 結果を検証
                assert len(tasks) == 1
                assert isinstance(tasks[0], Task)
                assert tasks[0].title == "テストタスク"

    @pytest.mark.asyncio
    async def test_get_tasks_exclude_completed(
        self, mock_config: NotionConfig, mock_database_schema: dict
    ) -> None:
        """完了済みタスクが除外され、実在する選択肢のみでフィルタが構築されることを確認."""
        empty_query_response = {
            "object": "list",
            "results": [],
            "next_cursor": None,
            "has_more": False,
        }

        def request_side_effect(*args: object, **kwargs: object) -> MagicMock:
            # メソッド/URLに応じてスキーマ取得とクエリを出し分ける
            method = kwargs.get("method")
            url = kwargs.get("url", "")
            mock_response = MagicMock()
            mock_response.status_code = 200
            if method == "GET" and not str(url).endswith("/query"):
                mock_response.json.return_value = mock_database_schema
            else:
                mock_response.json.return_value = empty_query_response
            return mock_response

        with patch("httpx.AsyncClient.request", side_effect=request_side_effect) as mock_request:
            async with NotionClient(mock_config) as client:
                await client.get_tasks(include_completed=False)

                # 最後の呼び出し（クエリ）のフィルタ条件を検証
                query_call = mock_request.call_args
                request_body = query_call.kwargs.get("json") or query_call.args[2]
                assert "filter" in request_body
                assert "and" in request_body["filter"]

                # 実在する「完了 🙌」のみが除外条件に含まれ、
                # 実在しない「キャンセル」は含まれないことを確認
                excluded_values = [
                    cond["status"]["does_not_equal"]
                    for cond in request_body["filter"]["and"]
                ]
                assert "完了 🙌" in excluded_values
                assert "キャンセル" not in excluded_values

    @pytest.mark.asyncio
    async def test_get_tasks_schema_fetch_failure_still_excludes_completed(
        self, mock_config: NotionConfig, mock_notion_page: dict
    ) -> None:
        """スキーマ取得が失敗しても、完了タスクがクライアント側で除外されることを確認."""
        completed_page = json.loads(json.dumps(mock_notion_page))
        completed_page["id"] = "completed-page"
        completed_page["properties"]["Status"]["status"]["name"] = "完了 🙌"

        query_response = {
            "object": "list",
            "results": [mock_notion_page, completed_page],
            "next_cursor": None,
            "has_more": False,
        }

        def request_side_effect(*args: object, **kwargs: object) -> MagicMock:
            method = kwargs.get("method")
            url = kwargs.get("url", "")
            mock_response = MagicMock()
            if method == "GET" and not str(url).endswith("/query"):
                # スキーマ取得は失敗させる（404）
                mock_response.status_code = 404
                mock_response.json.return_value = {
                    "object": "error",
                    "status": 404,
                    "message": "Not found",
                }
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = query_response
            return mock_response

        with patch("httpx.AsyncClient.request", side_effect=request_side_effect):
            async with NotionClient(mock_config) as client:
                tasks = await client.get_tasks(include_completed=False)

                # スキーマ取得失敗でサーバー側フィルタが効かなくても、
                # 完了タスクはクライアント側で除外される
                statuses = [task.status.value for task in tasks]
                assert "完了 🙌" not in statuses
                assert "対応中" in statuses

    @pytest.mark.asyncio
    async def test_update_page_success(self, mock_config: NotionConfig) -> None:
        """ページの更新が成功することを確認."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "object": "page",
                "id": "test-page-id",
                "properties": {"Status": {"status": {"name": "Completed"}}},
                "created_time": "2025-01-15T10:00:00.000Z",
                "last_edited_time": "2025-02-03T10:30:00.000Z",
                "archived": False,
                "url": "https://www.notion.so/test-page-id",
            }
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                properties = {
                    "Status": {"type": "status", "status": {"name": "Completed"}}
                }
                result = await client.update_page("test-page-id", properties)

                assert result["id"] == "test-page-id"

    @pytest.mark.asyncio
    async def test_update_task_status_success(
        self, mock_config: NotionConfig, mock_notion_page: dict
    ) -> None:
        """タスクのステータス更新が成功することを確認."""
        # ステータスを更新したページデータを作成
        updated_page = mock_notion_page.copy()
        updated_page["properties"]["Status"]["status"]["name"] = "完了 🙌"  # 日本語ステータス

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = updated_page
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                task = await client.update_task_status(
                    "test-page-id", TaskStatus.COMPLETED
                )

                assert task.status == TaskStatus.COMPLETED
                assert task.id == "test-page-id-123"

    @pytest.mark.asyncio
    async def test_update_task_success(
        self, mock_config: NotionConfig, mock_notion_page: dict
    ) -> None:
        """タスクの更新が成功することを確認."""
        updated_page = mock_notion_page.copy()
        updated_page["properties"]["Status"]["status"]["name"] = "完了 🙌"  # 日本語ステータス
        updated_page["properties"]["Priority"]["select"]["name"] = "Low"

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = updated_page
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                task = await client.update_task(
                    page_id="test-page-id",
                    status=TaskStatus.COMPLETED,
                    priority=TaskPriority.LOW,
                )

                assert task.status == TaskStatus.COMPLETED
                assert task.priority == TaskPriority.LOW

    @pytest.mark.asyncio
    async def test_update_task_no_properties(self, mock_config: NotionConfig) -> None:
        """更新するプロパティがない場合のエラーを確認."""
        async with NotionClient(mock_config) as client:
            with pytest.raises(ValueError, match="At least one property"):
                await client.update_task(page_id="test-page-id")

    @pytest.mark.asyncio
    async def test_create_page_success(self, mock_config: NotionConfig) -> None:
        """ページの作成が成功することを確認."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "object": "page",
                "id": "new-page-id",
                "created_time": "2025-02-03T10:00:00.000Z",
                "last_edited_time": "2025-02-03T10:00:00.000Z",
                "archived": False,
                "properties": {},
                "url": "https://www.notion.so/new-page-id",
            }
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                properties = {
                    "Title": {
                        "type": "title",
                        "title": [{"type": "text", "text": {"content": "New Page"}}],
                    }
                }
                result = await client.create_page("database-id", properties)

                assert result["id"] == "new-page-id"

    @pytest.mark.asyncio
    async def test_create_task_success(
        self, mock_config: NotionConfig, mock_notion_page: dict
    ) -> None:
        """タスクの作成が成功することを確認."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_notion_page
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                task = await client.create_task(
                    title="新しいタスク",
                    status=TaskStatus.NOT_STARTED,
                    priority=TaskPriority.HIGH,
                    due_date="2025-02-15",
                    tags=["test", "urgent"],
                )

                assert task.title == "テストタスク"  # mock_notion_pageのタイトル
                assert task.id == "test-page-id-123"

    @pytest.mark.asyncio
    async def test_create_memo_success(self, mock_config: NotionConfig) -> None:
        """メモの作成が成功することを確認."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "object": "page",
                "id": "memo-page-id",
                "created_time": "2025-02-03T10:00:00.000Z",
                "last_edited_time": "2025-02-03T10:00:00.000Z",
                "archived": False,
                "properties": {},
                "url": "https://www.notion.so/memo-page-id",
            }
            mock_request.return_value = mock_response

            async with NotionClient(mock_config) as client:
                memo = await client.create_memo(
                    title="テストメモ",
                    content="メモの内容です。",
                    tags=["meeting", "notes"],
                )

                assert memo["id"] == "memo-page-id"
                assert memo["url"] == "https://www.notion.so/memo-page-id"
