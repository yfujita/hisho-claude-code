"""Tests for config module.

NotionConfigの設定読み込みとバリデーションをテストします。
"""

import pytest
from pydantic import ValidationError

from src.config import NotionConfig


class TestNotionConfig:
    """NotionConfigクラスのテスト."""

    def test_initialization_with_valid_values(self, mock_config: NotionConfig) -> None:
        """有効な値で初期化できることを確認."""
        assert mock_config.notion_api_key.startswith("secret_test_")
        assert mock_config.notion_task_database_id.startswith("test-task-")
        assert mock_config.notion_memo_database_id.startswith("test-memo-")
        assert mock_config.mcp_log_level == "DEBUG"

    def test_default_values(self, mock_config: NotionConfig) -> None:
        """デフォルト値が正しく設定されることを確認."""
        assert mock_config.notion_api_version == "2022-06-28"
        assert mock_config.notion_base_url == "https://api.notion.com/v1"
        assert mock_config.rate_limit_requests_per_second == 3.0
        assert mock_config.rate_limit_burst == 10

    def test_property_name_mapping_defaults(self) -> None:
        """プロパティ名マッピングのデフォルト値を確認."""
        # デフォルト値をテストするため、カスタム値なしで設定を作成
        config = NotionConfig(
            notion_api_key="secret_test_key",
            notion_task_database_id="test-task-db-id",
            notion_memo_database_id="test-memo-db-id",
        )
        assert config.task_prop_title == "Name"
        assert config.task_prop_status == "ステータス"
        assert config.memo_prop_title == "名前"
        assert config.memo_prop_tags == "タグ"

    def test_headers_property(self, mock_config: NotionConfig) -> None:
        """headersプロパティが正しいヘッダーを返すことを確認."""
        headers = mock_config.headers
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Notion-Version"] == mock_config.notion_api_version
        assert headers["Content-Type"] == "application/json"

    def test_missing_required_field(self) -> None:
        """必須フィールドが欠けている場合にエラーが発生することを確認."""
        with pytest.raises(ValidationError):
            # notion_api_keyが欠けている
            NotionConfig(
                notion_task_database_id="test-db-id",
                notion_memo_database_id="test-memo-id",
            )

    def test_custom_property_names(self) -> None:
        """カスタムプロパティ名が設定できることを確認."""
        config = NotionConfig(
            notion_api_key="test-key",
            notion_task_database_id="test-task-db",
            notion_memo_database_id="test-memo-db",
            task_prop_title="タイトル",
            task_prop_status="Status",
            task_prop_priority="Priority",
            task_prop_due_date="DueDate",
            task_prop_tags="Tags",
        )

        assert config.task_prop_title == "タイトル"
        assert config.task_prop_status == "Status"
        assert config.task_prop_priority == "Priority"
        assert config.task_prop_due_date == "DueDate"
        assert config.task_prop_tags == "Tags"

    def test_empty_optional_fields(self) -> None:
        """オプショナルフィールドが空文字列でも動作することを確認."""
        config = NotionConfig(
            notion_api_key="test-key",
            notion_task_database_id="test-task-db",
            notion_memo_database_id="test-memo-db",
            task_prop_priority="",  # 空文字列（使用しない）
            task_prop_due_date="",
            task_prop_tags="",
        )

        assert config.task_prop_priority == ""
        assert config.task_prop_due_date == ""
        assert config.task_prop_tags == ""
