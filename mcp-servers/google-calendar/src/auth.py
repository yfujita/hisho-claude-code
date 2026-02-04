"""Google Calendar OAuth 2.0 authentication implementation.

このモジュールは、Google Calendar APIの認証を管理します。
リフレッシュトークンを使用したアクセストークンの取得・更新を実装します。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .config import GoogleCalendarConfig
from .exceptions import (
    ConfigurationError,
    GoogleAuthenticationError,
    NetworkError,
    TimeoutError,
)

logger = logging.getLogger(__name__)


class GoogleCalendarAuth:
    """Google Calendar API認証を管理するクラス.

    リフレッシュトークンを使用してアクセストークンを取得・更新します。
    トークンの有効期限を管理し、必要に応じて自動更新を行います。

    Args:
        config: Google Calendar設定

    Example:
        >>> config = GoogleCalendarConfig()
        >>> auth = GoogleCalendarAuth(config)
        >>> access_token = await auth.get_access_token()
    """

    def __init__(self, config: GoogleCalendarConfig) -> None:
        """GoogleCalendarAuthを初期化.

        Args:
            config: Google Calendar設定
        """
        self.config = config
        self._access_token: Optional[str] = config.google_access_token or None
        self._token_expiry: Optional[datetime] = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """HTTPクライアントを閉じる.

        リソースを解放するために、使用後に呼び出す必要があります。
        """
        await self._client.aclose()

    async def __aenter__(self) -> "GoogleCalendarAuth":
        """コンテキストマネージャーの開始（async with用）.

        Returns:
            GoogleCalendarAuth: 自身のインスタンス
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """コンテキストマネージャーの終了（async with用）.

        Args:
            exc_type: 例外の型
            exc_val: 例外の値
            exc_tb: トレースバック
        """
        await self.close()

    def is_token_expired(self) -> bool:
        """トークンの有効期限を確認.

        Returns:
            bool: トークンが期限切れまたは存在しない場合はTrue
        """
        if not self._access_token or not self._token_expiry:
            return True

        # 有効期限の5分前に期限切れと判定（安全マージン）
        return datetime.utcnow() >= self._token_expiry - timedelta(minutes=5)

    async def get_access_token(self) -> str:
        """有効なアクセストークンを取得（必要に応じて更新）.

        トークンが期限切れの場合、リフレッシュトークンを使用して
        新しいアクセストークンを取得します。

        Returns:
            str: アクセストークン

        Raises:
            GoogleAuthenticationError: 認証に失敗した場合
            NetworkError: ネットワークエラーが発生した場合
        """
        if self.is_token_expired():
            logger.info("Access token expired or missing. Refreshing token...")
            await self.refresh_access_token()

        if not self._access_token:
            raise GoogleAuthenticationError(
                message="アクセストークンの取得に失敗しました",
                details={"reason": "Token refresh did not set access token"},
            )

        return self._access_token

    async def refresh_access_token(self) -> str:
        """リフレッシュトークンを使用してアクセストークンを更新.

        Google OAuth 2.0トークンエンドポイントにリクエストを送信し、
        新しいアクセストークンを取得します。

        Returns:
            str: 新しいアクセストークン

        Raises:
            GoogleAuthenticationError: 認証に失敗した場合
            NetworkError: ネットワークエラーが発生した場合
            ConfigurationError: 必要な認証情報が設定されていない場合
        """
        # 必要な認証情報の確認
        if not self.config.google_client_id:
            raise ConfigurationError(
                message="Google Client IDが設定されていません",
                config_key="GOOGLE_CLIENT_ID",
            )
        if not self.config.google_client_secret:
            raise ConfigurationError(
                message="Google Client Secretが設定されていません",
                config_key="GOOGLE_CLIENT_SECRET",
            )
        if not self.config.google_refresh_token:
            raise ConfigurationError(
                message="Google Refresh Tokenが設定されていません",
                config_key="GOOGLE_REFRESH_TOKEN",
            )

        # リクエストボディの構築
        request_data = {
            "client_id": self.config.google_client_id,
            "client_secret": self.config.google_client_secret,
            "refresh_token": self.config.google_refresh_token,
            "grant_type": "refresh_token",
        }

        logger.debug(
            f"Requesting new access token from {self.config.google_token_uri}"
        )

        try:
            response = await self._client.post(
                self.config.google_token_uri,
                data=request_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # エラーレスポンスのハンドリング
            if response.status_code >= 400:
                self._handle_token_error_response(response)

            # レスポンスのパース
            token_data = response.json()

            # アクセストークンの取得
            access_token = token_data.get("access_token")
            if not access_token:
                raise GoogleAuthenticationError(
                    message="レスポンスにアクセストークンが含まれていません",
                    details={"response": token_data},
                )

            # トークンの有効期限を計算（デフォルト: 3600秒）
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

            # トークンを保存
            self._access_token = access_token

            logger.info(
                f"Successfully refreshed access token. Expires in {expires_in} seconds."
            )

            return access_token

        except httpx.TimeoutException as e:
            raise TimeoutError(
                message="トークン更新リクエストがタイムアウトしました",
                timeout_seconds=30.0,
                original_error=e,
            )
        except httpx.RequestError as e:
            raise NetworkError(
                message="トークン更新中にネットワークエラーが発生しました",
                details={"token_uri": self.config.google_token_uri},
                original_error=e,
            )
        except json.JSONDecodeError as e:
            raise GoogleAuthenticationError(
                message="トークンレスポンスのパースに失敗しました",
                details={"response_text": response.text[:200]},
                original_error=e,
            )

    def _handle_token_error_response(self, response: httpx.Response) -> None:
        """トークン取得エラーレスポンスを処理.

        Args:
            response: HTTPレスポンス

        Raises:
            GoogleAuthenticationError: 認証エラー
        """
        try:
            error_data = response.json()
            error_message = error_data.get("error_description", error_data.get("error", "Unknown error"))
            error_code = error_data.get("error", "unknown_error")
        except json.JSONDecodeError:
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"
            error_code = "parse_error"

        logger.error(
            f"Token refresh failed: {error_message}",
            extra={
                "extra_fields": {
                    "status_code": response.status_code,
                    "error_code": error_code,
                }
            },
        )

        raise GoogleAuthenticationError(
            message=f"アクセストークンの更新に失敗しました: {error_message}",
            details={
                "status_code": response.status_code,
                "error_code": error_code,
            },
        )

    def get_credentials_dict(self) -> dict[str, str]:
        """認証情報を辞書形式で返す.

        Returns:
            dict[str, str]: 認証情報（client_id, client_secret, refresh_token, access_token）
        """
        return {
            "client_id": self.config.google_client_id,
            "client_secret": self.config.google_client_secret,
            "refresh_token": self.config.google_refresh_token,
            "access_token": self._access_token or "",
            "token_uri": self.config.google_token_uri,
        }
