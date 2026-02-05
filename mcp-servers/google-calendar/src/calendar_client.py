"""Google Calendar API Client implementation.

このモジュールは、Google Calendar APIとの通信を行うクライアントを実装しています。
レート制限、エラーハンドリング、リトライ処理を含みます。
"""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from .auth import GoogleCalendarAuth
from .config import GoogleCalendarConfig
from .exceptions import (
    DataParsingError,
    GoogleAuthenticationError,
    GoogleNotFoundError,
    GooglePermissionError,
    GoogleRateLimitError,
    GoogleServerError,
    GoogleValidationError,
    NetworkError,
    TimeoutError,
)
from .models import Calendar, CalendarEvent
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Google Calendar APIクライアント.

    Google Calendar APIとの通信を行い、イベントのCRUD操作を実装します。
    レート制限、エラーハンドリング、リトライ処理を含みます。

    Args:
        config: Google Calendar設定
        auth: 認証マネージャー（Noneの場合は自動作成）
        rate_limiter: レート制限（Noneの場合は自動作成）

    Example:
        >>> config = GoogleCalendarConfig()
        >>> async with GoogleCalendarClient(config) as client:
        ...     events = await client.list_events()
    """

    def __init__(
        self,
        config: GoogleCalendarConfig,
        auth: Optional[GoogleCalendarAuth] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        """GoogleCalendarClientを初期化.

        Args:
            config: Google Calendar設定
            auth: 認証マネージャー（Noneの場合は設定から自動作成）
            rate_limiter: レート制限（Noneの場合は設定から自動作成）
        """
        self.config = config
        self.auth = auth or GoogleCalendarAuth(config)
        self.rate_limiter = rate_limiter or RateLimiter(
            tokens_per_second=config.rate_limit_requests_per_second,
            capacity=config.rate_limit_burst,
        )

        # ベースURL: https://www.googleapis.com/calendar/v3
        self.base_url = f"https://www.googleapis.com/{config.google_api_service_name}/{config.google_api_version}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60.0,
        )

    async def close(self) -> None:
        """HTTPクライアントと認証マネージャーを閉じる.

        リソースを解放するために、使用後に呼び出す必要があります。
        """
        await self.client.aclose()
        await self.auth.close()

    async def __aenter__(self) -> "GoogleCalendarClient":
        """コンテキストマネージャーの開始（async with用）.

        Returns:
            GoogleCalendarClient: 自身のインスタンス
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

    async def _get_headers(self) -> dict[str, str]:
        """APIリクエスト用のヘッダーを取得.

        Returns:
            dict[str, str]: HTTPヘッダー（認証トークンを含む）
        """
        access_token = await self.auth.get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        """Google Calendar APIへのリクエストを実行.

        レート制限、エラーハンドリング、リトライ処理（指数バックオフ）を含みます。

        Args:
            method: HTTPメソッド（GET、POST、PATCHなど）
            endpoint: APIエンドポイント（ベースURLからの相対パス）
            json_data: リクエストボディ（JSON）
            params: クエリパラメータ
            max_retries: 最大リトライ回数

        Returns:
            dict[str, Any]: APIレスポンス（JSON）

        Raises:
            GoogleAuthenticationError: 認証エラー（401）
            GooglePermissionError: 権限エラー（403）
            GoogleNotFoundError: リソース未検出（404）
            GoogleRateLimitError: レート制限エラー（429）
            GoogleValidationError: バリデーションエラー（400）
            GoogleServerError: サーバーエラー（5xx）
            NetworkError: ネットワークエラー
        """
        for attempt in range(max_retries):
            try:
                # レート制限を適用
                async with self.rate_limiter:
                    # 認証ヘッダーを取得
                    headers = await self._get_headers()

                    # リクエストログ
                    full_url = f"{self.base_url}/{endpoint}"
                    logger.debug(
                        f"Request: {method} {full_url}",
                        extra={
                            "extra_fields": {
                                "method": method,
                                "endpoint": endpoint,
                                "params": params,
                                "attempt": attempt + 1,
                            }
                        },
                    )

                    response = await self.client.request(
                        method=method,
                        url=endpoint,
                        json=json_data,
                        params=params,
                        headers=headers,
                    )

                    # レスポンスログ
                    logger.debug(
                        f"Response: {response.status_code}",
                        extra={
                            "extra_fields": {
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                            }
                        },
                    )

                    # レート制限エラー（429）のハンドリング
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            # 指数バックオフ
                            wait_time = 2**attempt
                            retry_after = int(response.headers.get("Retry-After", wait_time))
                            logger.warning(
                                f"Rate limited. Retrying after {retry_after} seconds... "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                            await self.rate_limiter.acquire()  # トークンを待機
                            continue
                        else:
                            self._handle_error_response(response)

                    # サーバーエラー（5xx）のハンドリング
                    if response.status_code >= 500:
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Server error ({response.status_code}). "
                                f"Retrying in {wait_time} seconds... "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                            continue
                        else:
                            self._handle_error_response(response)

                    # クライアントエラー（4xx）のハンドリング
                    if response.status_code >= 400:
                        self._handle_error_response(response)

                    # 成功レスポンス（2xx）
                    # 204 No Content の場合は空辞書を返す
                    if response.status_code == 204:
                        return {}

                    try:
                        return response.json()
                    except ValueError as e:
                        raise DataParsingError(
                            message="レスポンスのJSONパースに失敗しました",
                            details={
                                "status_code": response.status_code,
                                "response_text": response.text[:200],
                            },
                            original_error=e,
                        )

            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Timeout error. Retrying in {wait_time} seconds... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    continue
                else:
                    raise TimeoutError(
                        message="Google Calendar APIへのリクエストがタイムアウトしました",
                        timeout_seconds=60.0,
                        original_error=e,
                    )
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Request error: {e}. Retrying in {wait_time} seconds... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    continue
                else:
                    raise NetworkError(
                        message="Google Calendar APIへのネットワーク接続に失敗しました",
                        details={"endpoint": endpoint, "method": method},
                        original_error=e,
                    )

        raise NetworkError(
            message=f"最大リトライ回数（{max_retries}）を超過しました",
            details={"endpoint": endpoint, "method": method},
        )

    def _handle_error_response(self, response: httpx.Response) -> None:
        """エラーレスポンスを処理.

        Args:
            response: HTTPレスポンス

        Raises:
            GoogleAuthenticationError: 認証エラー（401）
            GooglePermissionError: 権限エラー（403）
            GoogleNotFoundError: リソース未検出（404）
            GoogleRateLimitError: レート制限エラー（429）
            GoogleValidationError: バリデーションエラー（400）
            GoogleServerError: サーバーエラー（5xx）
        """
        try:
            error_data = response.json()
            # Google Calendar APIのエラー形式: {"error": {"code": 404, "message": "...", ...}}
            error_info = error_data.get("error", {})
            status_code = error_info.get("code", response.status_code)
            message = error_info.get("message", "An unknown error occurred")
            errors = error_info.get("errors", [])
        except ValueError:
            # JSONパースエラーの場合
            raise DataParsingError(
                message=f"エラーレスポンスのパースに失敗しました: {response.text[:200]}",
                details={"status_code": response.status_code},
            )

        # ステータスコードに応じて適切な例外を発生させる
        if status_code == 401:
            raise GoogleAuthenticationError(
                message=f"認証エラー: {message}",
                details={"errors": errors},
            )
        elif status_code == 403:
            raise GooglePermissionError(
                message=f"権限エラー: {message}",
                details={"errors": errors},
            )
        elif status_code == 404:
            raise GoogleNotFoundError(
                message=f"リソースが見つかりません: {message}",
                details={"errors": errors},
            )
        elif status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            raise GoogleRateLimitError(
                message=f"レート制限エラー: {message}",
                retry_after=retry_after,
                details={"errors": errors},
            )
        elif status_code == 400:
            raise GoogleValidationError(
                message=f"バリデーションエラー: {message}",
                details={"errors": errors},
            )
        elif status_code >= 500:
            raise GoogleServerError(
                message=f"サーバーエラー: {message}",
                status_code=status_code,
                details={"errors": errors},
            )
        else:
            # その他のエラー
            raise GoogleServerError(
                message=f"APIエラー: {message}",
                status_code=status_code,
                details={"errors": errors},
            )

    async def list_calendars(self) -> list[Calendar]:
        """カレンダー一覧を取得.

        ユーザーがアクセス可能なカレンダーの一覧を取得します。

        Returns:
            list[Calendar]: カレンダーのリスト

        Raises:
            GoogleAuthenticationError: 認証エラー
            GooglePermissionError: 権限エラー
            GoogleRateLimitError: レート制限エラー

        Example:
            >>> calendars = await client.list_calendars()
            >>> for calendar in calendars:
            ...     print(f"{calendar.summary} ({calendar.id})")
        """
        endpoint = "users/me/calendarList"

        logger.info("Listing calendars")

        response_data = await self._request("GET", endpoint)

        # カレンダーリストの取得
        items = response_data.get("items", [])

        # Calendarモデルに変換
        calendars: list[Calendar] = []
        for item in items:
            try:
                calendar = Calendar(**item)
                calendars.append(calendar)
            except Exception as e:
                # パースエラーの場合は警告を出力してスキップ
                logger.warning(
                    f"Failed to parse calendar {item.get('id', 'unknown')}: {e}",
                    extra={
                        "extra_fields": {
                            "calendar_id": item.get("id"),
                            "error": str(e),
                        }
                    },
                )
                continue

        logger.info(f"Retrieved {len(calendars)} calendars")
        return calendars

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 10,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> list[CalendarEvent]:
        """イベント一覧を取得.

        Args:
            calendar_id: カレンダーID（デフォルト: "primary"）
            time_min: 開始時刻の下限（ISO 8601形式）
            time_max: 開始時刻の上限（ISO 8601形式）
            max_results: 最大取得件数（デフォルト: 10）
            single_events: 定期イベントを個別のインスタンスに展開するか（デフォルト: True）
            order_by: ソート順（"startTime" または "updated"）

        Returns:
            list[CalendarEvent]: イベントのリスト

        Raises:
            GoogleAuthenticationError: 認証エラー
            GooglePermissionError: 権限エラー
            GoogleNotFoundError: カレンダーが見つからない
            GoogleRateLimitError: レート制限エラー

        Example:
            >>> from datetime import datetime, timedelta
            >>> now = datetime.utcnow()
            >>> end = now + timedelta(days=7)
            >>> events = await client.list_events(
            ...     time_min=now,
            ...     time_max=end,
            ...     max_results=20
            ... )
        """
        endpoint = f"calendars/{calendar_id}/events"

        # クエリパラメータの構築
        params: dict[str, Any] = {
            "maxResults": max_results,
            "singleEvents": single_events,
        }

        if time_min:
            params["timeMin"] = time_min.isoformat()

        if time_max:
            params["timeMax"] = time_max.isoformat()

        if single_events and order_by:
            params["orderBy"] = order_by

        logger.info(
            f"Listing events from calendar '{calendar_id}'",
            extra={
                "extra_fields": {
                    "calendar_id": calendar_id,
                    "time_min": time_min,
                    "time_max": time_max,
                    "max_results": max_results,
                }
            },
        )

        response_data = await self._request("GET", endpoint, params=params)

        # イベントリストの取得
        items = response_data.get("items", [])

        # CalendarEventモデルに変換
        events: list[CalendarEvent] = []
        for item in items:
            try:
                event = self._parse_event(item)
                events.append(event)
            except DataParsingError as e:
                logger.warning(
                    f"Failed to parse event {item.get('id', 'unknown')}: {e}",
                    extra={
                        "extra_fields": {
                            "event_id": item.get("id"),
                            "error": str(e),
                        }
                    },
                )
                continue

        logger.info(f"Retrieved {len(events)} events")
        return events

    async def get_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> CalendarEvent:
        """イベント詳細を取得.

        Args:
            event_id: イベントID
            calendar_id: カレンダーID（デフォルト: "primary"）

        Returns:
            CalendarEvent: イベント

        Raises:
            GoogleAuthenticationError: 認証エラー
            GooglePermissionError: 権限エラー
            GoogleNotFoundError: イベントが見つからない
        """
        endpoint = f"calendars/{calendar_id}/events/{event_id}"

        logger.info(
            f"Getting event '{event_id}' from calendar '{calendar_id}'",
            extra={
                "extra_fields": {
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                }
            },
        )

        response_data = await self._request("GET", endpoint)
        return self._parse_event(response_data)

    async def create_event(
        self, event: CalendarEvent, calendar_id: str = "primary"
    ) -> CalendarEvent:
        """イベントを作成.

        Args:
            event: 作成するイベント
            calendar_id: カレンダーID（デフォルト: "primary"）

        Returns:
            CalendarEvent: 作成されたイベント

        Raises:
            GoogleAuthenticationError: 認証エラー
            GooglePermissionError: 権限エラー
            GoogleValidationError: バリデーションエラー
        """
        endpoint = f"calendars/{calendar_id}/events"

        # イベントデータをGoogle Calendar API形式に変換
        event_data = self._event_to_api_format(event)

        logger.info(
            f"Creating event '{event.summary}' in calendar '{calendar_id}'",
            extra={
                "extra_fields": {
                    "calendar_id": calendar_id,
                    "event_summary": event.summary,
                }
            },
        )

        response_data = await self._request("POST", endpoint, json_data=event_data)
        return self._parse_event(response_data)

    async def update_event(
        self, event_id: str, updates: dict[str, Any], calendar_id: str = "primary"
    ) -> CalendarEvent:
        """イベントを更新（PATCH: 部分更新）.

        Args:
            event_id: イベントID
            updates: 更新するフィールド
            calendar_id: カレンダーID（デフォルト: "primary"）

        Returns:
            CalendarEvent: 更新後のイベント

        Raises:
            GoogleAuthenticationError: 認証エラー
            GooglePermissionError: 権限エラー
            GoogleNotFoundError: イベントが見つからない
            GoogleValidationError: バリデーションエラー

        Example:
            >>> await client.update_event(
            ...     event_id="event123",
            ...     updates={"summary": "新しいタイトル", "location": "新しい場所"}
            ... )
        """
        endpoint = f"calendars/{calendar_id}/events/{event_id}"

        logger.info(
            f"Updating event '{event_id}' in calendar '{calendar_id}'",
            extra={
                "extra_fields": {
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                    "updates": list(updates.keys()),
                }
            },
        )

        response_data = await self._request("PATCH", endpoint, json_data=updates)
        return self._parse_event(response_data)

    def _parse_event(self, event_data: dict[str, Any]) -> CalendarEvent:
        """APIレスポンスをCalendarEventモデルに変換.

        Args:
            event_data: Google Calendar APIのイベントデータ

        Returns:
            CalendarEvent: イベントモデル

        Raises:
            DataParsingError: パースに失敗した場合
        """
        try:
            # Pydanticモデルでバリデーション
            # Google Calendar APIのフィールド名はcamelCase、
            # モデル側でエイリアス設定により自動変換される
            return CalendarEvent(**event_data)
        except Exception as e:
            raise DataParsingError(
                message="イベントデータのパースに失敗しました",
                details={
                    "event_id": event_data.get("id"),
                    "error": str(e),
                },
                original_error=e,
            )

    def _event_to_api_format(self, event: CalendarEvent) -> dict[str, Any]:
        """CalendarEventモデルをGoogle Calendar API形式に変換.

        Args:
            event: イベントモデル

        Returns:
            dict[str, Any]: API形式のイベントデータ
        """
        # Pydanticモデルのmodel_dumpを使用してJSON互換辞書に変換
        # by_alias=Trueで、フィールド名のエイリアス（camelCase）を使用
        event_dict = event.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
        )

        # IDフィールドは作成時には不要なので削除
        event_dict.pop("id", None)

        return event_dict
