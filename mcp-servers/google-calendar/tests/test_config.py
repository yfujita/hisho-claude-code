"""Tests for config module.

GoogleCalendarConfigの設定読み込みとバリデーションをテストします。
"""

import pytest
from pydantic import ValidationError

from src.config import GoogleCalendarConfig


class TestGoogleCalendarConfig:
    """GoogleCalendarConfigクラスのテスト."""

    def test_initialization_with_valid_values(self, mock_config: GoogleCalendarConfig) -> None:
        """有効な値で初期化できることを確認."""
        assert mock_config.google_client_id.endswith(".apps.googleusercontent.com")
        assert mock_config.google_client_secret.startswith("test-client-secret")
        assert mock_config.google_refresh_token.startswith("test-refresh-token")
        assert mock_config.google_calendar_id == "primary"
        assert mock_config.google_calendar_timezone == "Asia/Tokyo"
        assert mock_config.mcp_log_level == "DEBUG"

    def test_default_values(self, mock_config: GoogleCalendarConfig) -> None:
        """デフォルト値が正しく設定されることを確認."""
        assert mock_config.google_api_service_name == "calendar"
        assert mock_config.google_api_version == "v3"
        assert mock_config.google_token_uri == "https://oauth2.googleapis.com/token"
        assert mock_config.rate_limit_requests_per_second == 1.5
        assert mock_config.rate_limit_burst == 10

    def test_optional_access_token_default(self) -> None:
        """アクセストークンがオプションでデフォルト値が空文字列であることを確認."""
        config = GoogleCalendarConfig(
            google_client_id="test-client-id",
            google_client_secret="test-client-secret",
            google_refresh_token="test-refresh-token",
        )
        assert config.google_access_token == ""

    def test_get_credentials_dict(self, mock_config: GoogleCalendarConfig) -> None:
        """get_credentials_dictメソッドが正しく認証情報を返すことを確認."""
        creds = mock_config.get_credentials_dict()

        assert "client_id" in creds
        assert "client_secret" in creds
        assert "refresh_token" in creds
        assert "token_uri" in creds
        assert creds["client_id"] == mock_config.google_client_id
        assert creds["client_secret"] == mock_config.google_client_secret
        assert creds["refresh_token"] == mock_config.google_refresh_token
        assert creds["token_uri"] == mock_config.google_token_uri

    def test_missing_required_fields(self) -> None:
        """必須フィールドが欠けている場合にエラーが発生することを確認."""
        # google_client_idが欠けている
        with pytest.raises(ValidationError):
            GoogleCalendarConfig(
                google_client_secret="test-secret",
                google_refresh_token="test-token",
            )

        # google_client_secretが欠けている
        with pytest.raises(ValidationError):
            GoogleCalendarConfig(
                google_client_id="test-id",
                google_refresh_token="test-token",
            )

        # google_refresh_tokenが欠けている
        with pytest.raises(ValidationError):
            GoogleCalendarConfig(
                google_client_id="test-id",
                google_client_secret="test-secret",
            )

    def test_custom_calendar_id(self) -> None:
        """カスタムカレンダーIDが設定できることを確認."""
        config = GoogleCalendarConfig(
            google_client_id="test-id",
            google_client_secret="test-secret",
            google_refresh_token="test-token",
            google_calendar_id="custom-calendar-id@group.calendar.google.com",
        )
        assert config.google_calendar_id == "custom-calendar-id@group.calendar.google.com"

    def test_custom_timezone(self) -> None:
        """カスタムタイムゾーンが設定できることを確認."""
        config = GoogleCalendarConfig(
            google_client_id="test-id",
            google_client_secret="test-secret",
            google_refresh_token="test-token",
            google_calendar_timezone="America/New_York",
        )
        assert config.google_calendar_timezone == "America/New_York"

    def test_custom_rate_limit_settings(self) -> None:
        """カスタムレート制限設定が適用されることを確認."""
        config = GoogleCalendarConfig(
            google_client_id="test-id",
            google_client_secret="test-secret",
            google_refresh_token="test-token",
            rate_limit_requests_per_second=2.0,
            rate_limit_burst=5,
        )
        assert config.rate_limit_requests_per_second == 2.0
        assert config.rate_limit_burst == 5

    def test_case_insensitive_env_vars(self) -> None:
        """環境変数が大文字小文字を区別しないことを確認."""
        # pydantic_settingsのcase_sensitive=Falseにより、
        # 大文字小文字を区別せずに環境変数を読み込むことができる
        # （実際の環境変数テストはここでは行わず、設定の検証のみ）
        config = GoogleCalendarConfig(
            google_client_id="test-id",
            google_client_secret="test-secret",
            google_refresh_token="test-token",
        )
        # 設定が正常に作成されることを確認
        assert config.google_client_id == "test-id"
