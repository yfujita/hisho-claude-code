"""Configuration management for Google Calendar MCP Server.

このモジュールは、環境変数から設定を読み込み、
アプリケーション全体で使用する設定を管理します。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleCalendarConfig(BaseSettings):
    """Google Calendar MCP Serverの設定.

    環境変数から設定を読み込みます。
    .envファイルを使用する場合は、プロジェクトルートに配置してください。
    """

    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    google_access_token: str = ""  # オプション（リフレッシュトークンから自動取得可能）
    google_calendar_id: str = "primary"  # デフォルトはプライマリカレンダー
    google_calendar_timezone: str = "Asia/Tokyo"  # デフォルトタイムゾーン
    mcp_log_level: str = "INFO"

    # Google Calendar APIの基本設定
    google_api_service_name: str = "calendar"
    google_api_version: str = "v3"
    google_token_uri: str = "https://oauth2.googleapis.com/token"

    # レート制限設定（Google Calendar APIの制限に準拠）
    # https://developers.google.com/calendar/api/guides/quota
    # 実際のクォータ: 毎分100リクエスト（1分あたり）
    # 安全マージンを考慮して、1秒あたり1.5リクエスト（90リクエスト/分）に設定
    rate_limit_requests_per_second: float = 1.5
    rate_limit_burst: int = 10  # バースト許容数

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_credentials_dict(self) -> dict[str, str]:
        """Google OAuth2認証情報を辞書形式で返す.

        Returns:
            dict[str, str]: 認証情報（client_id, client_secret, refresh_token）
        """
        return {
            "client_id": self.google_client_id,
            "client_secret": self.google_client_secret,
            "refresh_token": self.google_refresh_token,
            "token_uri": self.google_token_uri,
        }
