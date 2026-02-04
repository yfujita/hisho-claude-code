"""Tests for auth module.

Google Calendar OAuth 2.0認証の動作をテストします。
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.auth import GoogleCalendarAuth
from src.config import GoogleCalendarConfig
from src.exceptions import (
    ConfigurationError,
    GoogleAuthenticationError,
    NetworkError,
    TimeoutError,
)


class TestGoogleCalendarAuth:
    """GoogleCalendarAuthクラスのテスト."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config: GoogleCalendarConfig) -> None:
        """正常に初期化できることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        assert auth.config == mock_config
        assert auth._access_token == mock_config.google_access_token
        await auth.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config: GoogleCalendarConfig) -> None:
        """コンテキストマネージャーとして使用できることを確認."""
        async with GoogleCalendarAuth(mock_config) as auth:
            assert auth is not None
            assert isinstance(auth, GoogleCalendarAuth)

    def test_is_token_expired_no_token(self, mock_config: GoogleCalendarConfig) -> None:
        """トークンがない場合は期限切れと判定されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = None
        assert auth.is_token_expired() is True

    def test_is_token_expired_no_expiry(self, mock_config: GoogleCalendarConfig) -> None:
        """有効期限がない場合は期限切れと判定されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "valid-token"
        auth._token_expiry = None
        assert auth.is_token_expired() is True

    def test_is_token_expired_expired(self, mock_config: GoogleCalendarConfig) -> None:
        """有効期限を過ぎている場合は期限切れと判定されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "valid-token"
        # 1時間前に期限切れ
        auth._token_expiry = datetime.utcnow() - timedelta(hours=1)
        assert auth.is_token_expired() is True

    def test_is_token_expired_valid(self, mock_config: GoogleCalendarConfig) -> None:
        """有効期限内のトークンは有効と判定されることを確認（安全マージン考慮）."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "valid-token"
        # 10分後に期限切れ（5分マージンがあるため期限切れと判定される）
        auth._token_expiry = datetime.utcnow() + timedelta(minutes=10)
        assert auth.is_token_expired() is False

    def test_is_token_expired_within_margin(self, mock_config: GoogleCalendarConfig) -> None:
        """安全マージン内のトークンは期限切れと判定されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "valid-token"
        # 3分後に期限切れ（5分マージンがあるため期限切れと判定される）
        auth._token_expiry = datetime.utcnow() + timedelta(minutes=3)
        assert auth.is_token_expired() is True

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(
        self, mock_config: GoogleCalendarConfig, mock_token_response: dict
    ) -> None:
        """トークン更新が成功することを確認."""
        auth = GoogleCalendarAuth(mock_config)

        # httpx.AsyncClientのpostメソッドをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            token = await auth.refresh_access_token()

            assert token == mock_token_response["access_token"]
            assert auth._access_token == mock_token_response["access_token"]
            assert auth._token_expiry is not None
            mock_post.assert_called_once()

        await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_access_token_missing_client_id(
        self, mock_config: GoogleCalendarConfig
    ) -> None:
        """Client IDが欠けている場合にエラーが発生することを確認."""
        # Client IDを空にする
        mock_config.google_client_id = ""
        auth = GoogleCalendarAuth(mock_config)

        with pytest.raises(ConfigurationError) as exc_info:
            await auth.refresh_access_token()

        assert "Client ID" in str(exc_info.value)
        await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_access_token_http_error(
        self, mock_config: GoogleCalendarConfig
    ) -> None:
        """HTTP エラーレスポンスが正しく処理されることを確認."""
        auth = GoogleCalendarAuth(mock_config)

        # 401エラーレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked.",
        }

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(GoogleAuthenticationError) as exc_info:
                await auth.refresh_access_token()

            assert "Token has been expired or revoked" in str(exc_info.value)

        await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_access_token_timeout(
        self, mock_config: GoogleCalendarConfig
    ) -> None:
        """タイムアウトが正しく処理されることを確認."""
        auth = GoogleCalendarAuth(mock_config)

        with patch.object(
            auth._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(TimeoutError) as exc_info:
                await auth.refresh_access_token()

            assert "タイムアウト" in str(exc_info.value)

        await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_access_token_network_error(
        self, mock_config: GoogleCalendarConfig
    ) -> None:
        """ネットワークエラーが正しく処理されることを確認."""
        auth = GoogleCalendarAuth(mock_config)

        with patch.object(
            auth._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.RequestError("Network error")

            with pytest.raises(NetworkError) as exc_info:
                await auth.refresh_access_token()

            assert "ネットワーク" in str(exc_info.value)

        await auth.close()

    @pytest.mark.asyncio
    async def test_get_access_token_valid(self, mock_config: GoogleCalendarConfig) -> None:
        """有効なトークンが返されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "valid-token"
        auth._token_expiry = datetime.utcnow() + timedelta(hours=1)

        token = await auth.get_access_token()
        assert token == "valid-token"
        await auth.close()

    @pytest.mark.asyncio
    async def test_get_access_token_refresh_when_expired(
        self, mock_config: GoogleCalendarConfig, mock_token_response: dict
    ) -> None:
        """期限切れの場合に自動的にトークンが更新されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "old-token"
        auth._token_expiry = datetime.utcnow() - timedelta(hours=1)  # 期限切れ

        # リフレッシュトークンのモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            token = await auth.get_access_token()

            assert token == mock_token_response["access_token"]
            assert auth._access_token == mock_token_response["access_token"]
            mock_post.assert_called_once()

        await auth.close()

    def test_get_credentials_dict(self, mock_config: GoogleCalendarConfig) -> None:
        """認証情報が辞書形式で返されることを確認."""
        auth = GoogleCalendarAuth(mock_config)
        auth._access_token = "current-access-token"

        creds = auth.get_credentials_dict()

        assert creds["client_id"] == mock_config.google_client_id
        assert creds["client_secret"] == mock_config.google_client_secret
        assert creds["refresh_token"] == mock_config.google_refresh_token
        assert creds["access_token"] == "current-access-token"
        assert creds["token_uri"] == mock_config.google_token_uri
