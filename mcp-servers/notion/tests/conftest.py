"""Pytest configuration and fixtures.

このモジュールは、テスト全体で使用される共通のフィクスチャを定義します。
"""

import pytest

from src.config import NotionConfig
from src.rate_limiter import RateLimiter


@pytest.fixture
def mock_config() -> NotionConfig:
    """モックのNotion設定を返す.

    Returns:
        NotionConfig: テスト用の設定
    """
    # 環境変数を使わずに直接設定を作成
    # 実際のAPIキーは不要（テストではモックを使用）
    # プロパティ名はモックデータに合わせて英語名を指定
    return NotionConfig(
        notion_api_key="secret_test_api_key_xxxxxxxxxxxxxxxxxxxxxxxxxx",
        notion_task_database_id="test-task-database-id-xxxxxxxxxxxxxxxx",
        notion_memo_database_id="test-memo-database-id-xxxxxxxxxxxxxxxx",
        mcp_log_level="DEBUG",
        # テスト用のプロパティ名マッピング（モックデータに合わせる）
        task_prop_title="Title",
        task_prop_status="Status",
        task_prop_priority="Priority",
        task_prop_due_date="Due Date",
        task_prop_tags="Tags",
        memo_prop_title="Title",
        memo_prop_tags="Tags",
    )


@pytest.fixture
def rate_limiter() -> RateLimiter:
    """レート制限のインスタンスを返す.

    Returns:
        RateLimiter: テスト用のレート制限（高速設定）
    """
    # テスト用に高速なレート制限を設定
    return RateLimiter(tokens_per_second=100.0, capacity=10)
