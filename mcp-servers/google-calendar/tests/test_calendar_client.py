"""Tests for calendar_client module.

Google Calendar APIクライアントの動作をテストします。
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.auth import GoogleCalendarAuth
from src.calendar_client import GoogleCalendarClient
from src.config import GoogleCalendarConfig
from src.exceptions import (
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
from src.models import CalendarEvent, EventDateTime


class TestGoogleCalendarClient:
    """GoogleCalendarClientクラスのテスト."""

    @pytest.mark.asyncio
    async def test_initialization(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """正常に初期化できることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)
        assert client.config == mock_config
        assert client.base_url == "https://www.googleapis.com/calendar/v3"
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config: GoogleCalendarConfig) -> None:
        """コンテキストマネージャーとして使用できることを確認."""
        async with GoogleCalendarClient(mock_config) as client:
            assert client is not None
            assert isinstance(client, GoogleCalendarClient)

    @pytest.mark.asyncio
    async def test_get_headers(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """正しいヘッダーが生成されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        # アクセストークンをモック
        with patch.object(
            client.auth, "get_access_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = "test-access-token"

            headers = await client._get_headers()

            assert headers["Authorization"] == "Bearer test-access-token"
            assert headers["Content-Type"] == "application/json"
            assert headers["Accept"] == "application/json"

        await client.close()

    @pytest.mark.asyncio
    async def test_list_events_success(
        self,
        mock_config: GoogleCalendarConfig,
        rate_limiter,
        mock_events_list_response: dict,
    ) -> None:
        """イベント一覧取得が成功することを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        # APIレスポンスをモック
        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_events_list_response

            events = await client.list_events(
                calendar_id="primary",
                time_min=datetime.utcnow(),
                time_max=datetime.utcnow() + timedelta(days=7),
                max_results=10,
            )

            assert len(events) == 1
            assert isinstance(events[0], CalendarEvent)
            assert events[0].id == "event123abc"
            mock_request.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_list_events_empty_response(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """イベントが0件の場合の動作を確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        # 空のレスポンスをモック
        empty_response = {
            "kind": "calendar#events",
            "items": [],
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = empty_response

            events = await client.list_events()
            assert events == []

        await client.close()

    @pytest.mark.asyncio
    async def test_get_event_success(
        self,
        mock_config: GoogleCalendarConfig,
        rate_limiter,
        sample_event_dict: dict,
    ) -> None:
        """イベント詳細取得が成功することを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = sample_event_dict

            event = await client.get_event(event_id="event123abc")

            assert isinstance(event, CalendarEvent)
            assert event.id == "event123abc"
            assert event.summary == "ミーティング"
            mock_request.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_create_event_success(
        self,
        mock_config: GoogleCalendarConfig,
        rate_limiter,
        sample_event: CalendarEvent,
        sample_event_dict: dict,
    ) -> None:
        """イベント作成が成功することを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = sample_event_dict

            created_event = await client.create_event(event=sample_event)

            assert isinstance(created_event, CalendarEvent)
            assert created_event.id == "event123abc"
            mock_request.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_update_event_success(
        self,
        mock_config: GoogleCalendarConfig,
        rate_limiter,
        sample_event_dict: dict,
    ) -> None:
        """イベント更新が成功することを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        # 更新後のレスポンスをモック
        updated_dict = sample_event_dict.copy()
        updated_dict["summary"] = "更新されたミーティング"

        with patch.object(
            client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = updated_dict

            updates = {"summary": "更新されたミーティング"}
            updated_event = await client.update_event(
                event_id="event123abc", updates=updates
            )

            assert updated_event.summary == "更新されたミーティング"
            mock_request.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_request_authentication_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """認証エラー（401）が正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.json.return_value = {
            "error": {
                "code": 401,
                "message": "Invalid Credentials",
                "status": "UNAUTHENTICATED",
            }
        }

        # _get_headersをモックして、トークン更新処理をスキップ
        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_request.return_value = error_response

            with pytest.raises(GoogleAuthenticationError) as exc_info:
                await client._request("GET", "calendars/primary/events")

            assert "Invalid Credentials" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_request_permission_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """権限エラー（403）が正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        error_response = MagicMock()
        error_response.status_code = 403
        error_response.json.return_value = {
            "error": {
                "code": 403,
                "message": "Forbidden",
                "status": "PERMISSION_DENIED",
            }
        }

        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_request.return_value = error_response

            with pytest.raises(GooglePermissionError):
                await client._request("GET", "calendars/primary/events")

        await client.close()

    @pytest.mark.asyncio
    async def test_request_not_found_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """リソース未検出エラー（404）が正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        error_response = MagicMock()
        error_response.status_code = 404
        error_response.json.return_value = {
            "error": {
                "code": 404,
                "message": "Not Found",
                "status": "NOT_FOUND",
            }
        }

        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_request.return_value = error_response

            with pytest.raises(GoogleNotFoundError):
                await client._request("GET", "calendars/primary/events/nonexistent")

        await client.close()

    @pytest.mark.asyncio
    async def test_request_validation_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """バリデーションエラー（400）が正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        error_response = MagicMock()
        error_response.status_code = 400
        error_response.json.return_value = {
            "error": {
                "code": 400,
                "message": "Invalid request",
                "status": "INVALID_ARGUMENT",
            }
        }

        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_request.return_value = error_response

            with pytest.raises(GoogleValidationError):
                await client._request("POST", "calendars/primary/events")

        await client.close()

    @pytest.mark.asyncio
    async def test_request_server_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """サーバーエラー（500）が正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        error_response = MagicMock()
        error_response.status_code = 500
        error_response.json.return_value = {
            "error": {
                "code": 500,
                "message": "Internal Server Error",
                "status": "INTERNAL",
            }
        }

        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            # 最大リトライ回数を超えてもエラーが続く
            mock_request.return_value = error_response

            with pytest.raises(GoogleServerError):
                await client._request("GET", "calendars/primary/events", max_retries=1)

        await client.close()

    @pytest.mark.asyncio
    async def test_request_timeout_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """タイムアウトエラーが正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_request.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(TimeoutError):
                await client._request("GET", "calendars/primary/events", max_retries=1)

        await client.close()

    @pytest.mark.asyncio
    async def test_request_network_error(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """ネットワークエラーが正しく処理されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        with patch.object(
            client, "_get_headers", new_callable=AsyncMock
        ) as mock_get_headers, patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_get_headers.return_value = {"Authorization": "Bearer test-token"}
            mock_request.side_effect = httpx.RequestError("Connection error")

            with pytest.raises(NetworkError):
                await client._request("GET", "calendars/primary/events", max_retries=1)

        await client.close()

    @pytest.mark.asyncio
    async def test_parse_event_success(
        self,
        mock_config: GoogleCalendarConfig,
        rate_limiter,
        sample_event_dict: dict,
    ) -> None:
        """イベントデータのパースが成功することを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        event = client._parse_event(sample_event_dict)

        assert isinstance(event, CalendarEvent)
        assert event.id == sample_event_dict["id"]
        assert event.summary == sample_event_dict["summary"]
        await client.close()

    @pytest.mark.asyncio
    async def test_parse_event_invalid_data(
        self, mock_config: GoogleCalendarConfig, rate_limiter
    ) -> None:
        """不正なイベントデータのパースでエラーが発生することを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        # 必須フィールドが欠けているデータ
        invalid_data = {
            "id": "test",
            # startとendが欠けている
        }

        with pytest.raises(DataParsingError):
            client._parse_event(invalid_data)

        await client.close()

    @pytest.mark.asyncio
    async def test_event_to_api_format(
        self,
        mock_config: GoogleCalendarConfig,
        rate_limiter,
        sample_event: CalendarEvent,
    ) -> None:
        """イベントモデルがAPI形式に変換されることを確認."""
        client = GoogleCalendarClient(mock_config, rate_limiter=rate_limiter)

        api_format = client._event_to_api_format(sample_event)

        # IDフィールドは削除される
        assert "id" not in api_format
        assert "summary" in api_format
        assert "start" in api_format
        assert "end" in api_format
        await client.close()
