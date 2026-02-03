"""Tests for models module.

Pydanticモデルのバリデーションとシリアライゼーションをテストします。
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from src.models import (
    NotionDatabaseQueryResponse,
    NotionError,
    NotionPage,
    Task,
    TaskPriority,
    TaskStatus,
)


class TestTaskStatus:
    """TaskStatus enumのテスト."""

    def test_all_status_values(self) -> None:
        """すべてのステータス値が正しく定義されていることを確認."""
        assert TaskStatus.NOT_STARTED.value == "未着手"
        assert TaskStatus.TODAY.value == "今日やる"
        assert TaskStatus.IN_PROGRESS.value == "対応中"
        assert TaskStatus.BACKLOG.value == "バックログ"
        assert TaskStatus.COMPLETED.value == "完了 🙌"
        assert TaskStatus.CANCELLED.value == "キャンセル"

    def test_status_from_string(self) -> None:
        """文字列からステータスを作成できることを確認."""
        status = TaskStatus("未着手")
        assert status == TaskStatus.NOT_STARTED

    def test_invalid_status(self) -> None:
        """無効なステータス値でエラーが発生することを確認."""
        with pytest.raises(ValueError):
            TaskStatus("無効なステータス")


class TestTaskPriority:
    """TaskPriority enumのテスト."""

    def test_all_priority_values(self) -> None:
        """すべての優先度値が正しく定義されていることを確認."""
        assert TaskPriority.HIGH.value == "High"
        assert TaskPriority.MEDIUM.value == "Medium"
        assert TaskPriority.LOW.value == "Low"

    def test_priority_from_string(self) -> None:
        """文字列から優先度を作成できることを確認."""
        priority = TaskPriority("High")
        assert priority == TaskPriority.HIGH


class TestTask:
    """Taskモデルのテスト."""

    def test_create_task_with_all_fields(self) -> None:
        """全フィールドを指定してタスクを作成できることを確認."""
        task = Task(
            id="task-123",
            title="テストタスク",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            due_date=date(2025, 2, 15),
            tags=["urgent", "important"],
            created_time=datetime(2025, 1, 1, 10, 0, 0),
            last_edited_time=datetime(2025, 2, 1, 15, 30, 0),
            url="https://www.notion.so/task-123",
        )

        assert task.id == "task-123"
        assert task.title == "テストタスク"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == TaskPriority.HIGH
        assert task.due_date == date(2025, 2, 15)
        assert task.tags == ["urgent", "important"]
        assert task.url == "https://www.notion.so/task-123"

    def test_create_task_with_minimal_fields(self) -> None:
        """最小限のフィールドでタスクを作成できることを確認."""
        task = Task(
            id="task-456",
            title="シンプルなタスク",
            status=TaskStatus.NOT_STARTED,
            created_time=datetime(2025, 1, 1, 10, 0, 0),
            last_edited_time=datetime(2025, 1, 1, 10, 0, 0),
            url="https://www.notion.so/task-456",
        )

        assert task.id == "task-456"
        assert task.title == "シンプルなタスク"
        assert task.priority is None
        assert task.due_date is None
        assert task.tags == []

    def test_task_missing_required_field(self) -> None:
        """必須フィールドが欠けている場合にエラーが発生することを確認."""
        with pytest.raises(ValidationError):
            Task(
                id="task-789",
                title="タイトルのみ",
                # statusが欠けている
                created_time=datetime(2025, 1, 1, 10, 0, 0),
                last_edited_time=datetime(2025, 1, 1, 10, 0, 0),
                url="https://www.notion.so/task-789",
            )


class TestNotionPage:
    """NotionPageモデルのテスト."""

    def test_create_notion_page(self) -> None:
        """Notionページモデルを作成できることを確認."""
        page = NotionPage(
            object="page",
            id="page-123",
            created_time=datetime(2025, 1, 1, 10, 0, 0),
            last_edited_time=datetime(2025, 2, 1, 15, 30, 0),
            archived=False,
            properties={
                "Title": {
                    "id": "title",
                    "type": "title",
                    "title": [{"type": "text", "text": {"content": "ページタイトル"}}],
                }
            },
            url="https://www.notion.so/page-123",
        )

        assert page.object == "page"
        assert page.id == "page-123"
        assert page.archived is False
        assert "Title" in page.properties

    def test_notion_page_archived_default(self) -> None:
        """archivedフィールドのデフォルト値を確認."""
        page = NotionPage(
            object="page",
            id="page-456",
            created_time=datetime(2025, 1, 1, 10, 0, 0),
            last_edited_time=datetime(2025, 1, 1, 10, 0, 0),
            properties={},
            url="https://www.notion.so/page-456",
        )

        assert page.archived is False


class TestNotionDatabaseQueryResponse:
    """NotionDatabaseQueryResponseモデルのテスト."""

    def test_create_query_response(self) -> None:
        """データベースクエリレスポンスを作成できることを確認."""
        page = NotionPage(
            object="page",
            id="page-1",
            created_time=datetime(2025, 1, 1, 10, 0, 0),
            last_edited_time=datetime(2025, 1, 1, 10, 0, 0),
            archived=False,
            properties={},
            url="https://www.notion.so/page-1",
        )

        response = NotionDatabaseQueryResponse(
            object="list",
            results=[page],
            next_cursor="cursor-123",
            has_more=True,
        )

        assert response.object == "list"
        assert len(response.results) == 1
        assert response.next_cursor == "cursor-123"
        assert response.has_more is True

    def test_query_response_defaults(self) -> None:
        """デフォルト値が正しく設定されることを確認."""
        response = NotionDatabaseQueryResponse(
            object="list",
            results=[],
        )

        assert response.next_cursor is None
        assert response.has_more is False


class TestNotionError:
    """NotionErrorモデルのテスト."""

    def test_create_notion_error(self) -> None:
        """Notionエラーモデルを作成できることを確認."""
        error = NotionError(
            object="error",
            status=400,
            code="validation_error",
            message="Invalid request parameters",
        )

        assert error.object == "error"
        assert error.status == 400
        assert error.code == "validation_error"
        assert error.message == "Invalid request parameters"

    def test_notion_error_missing_field(self) -> None:
        """必須フィールドが欠けている場合にエラーが発生することを確認."""
        with pytest.raises(ValidationError):
            NotionError(
                object="error",
                status=400,
                # codeとmessageが欠けている
            )
