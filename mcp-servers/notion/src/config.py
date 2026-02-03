"""Configuration management for Notion MCP Server.

このモジュールは、環境変数から設定を読み込み、
アプリケーション全体で使用する設定を管理します。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class NotionConfig(BaseSettings):
    """Notion MCP Serverの設定.

    環境変数から設定を読み込みます。
    .envファイルを使用する場合は、プロジェクトルートに配置してください。
    """

    notion_api_key: str
    notion_task_database_id: str
    notion_memo_database_id: str
    mcp_log_level: str = "INFO"

    # Notion APIの基本設定
    notion_api_version: str = "2022-06-28"
    notion_base_url: str = "https://api.notion.com/v1"

    # レート制限設定
    rate_limit_requests_per_second: float = 3.0
    rate_limit_burst: int = 10

    # タスクDBのプロパティ名マッピング（環境変数でカスタマイズ可能）
    task_prop_title: str = "Name"
    task_prop_status: str = "ステータス"
    task_prop_priority: str = ""  # 空の場合はソート/フィルタで使用しない
    task_prop_due_date: str = ""  # 空の場合はソート/フィルタで使用しない
    task_prop_tags: str = ""  # 空の場合は使用しない

    # メモDBのプロパティ名マッピング
    memo_prop_title: str = "名前"
    memo_prop_tags: str = "タグ"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def headers(self) -> dict[str, str]:
        """Notion APIリクエスト用のヘッダーを返す.

        Returns:
            dict[str, str]: Authorization、Notion-Version、Content-Typeヘッダー
        """
        return {
            "Authorization": f"Bearer {self.notion_api_key}",
            "Notion-Version": self.notion_api_version,
            "Content-Type": "application/json",
        }
