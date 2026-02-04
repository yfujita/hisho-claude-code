"""Tests for exceptions module.

カスタム例外クラスの動作をテストします。
"""

import pytest

from src.exceptions import (
    ConfigurationError,
    DataParsingError,
    GoogleAuthenticationError,
    GoogleCalendarAPIError,
    GoogleCalendarMCPError,
    GoogleNotFoundError,
    GooglePermissionError,
    GoogleRateLimitError,
    GoogleServerError,
    GoogleValidationError,
    NetworkError,
    TimeoutError,
)


class TestGoogleCalendarMCPError:
    """GoogleCalendarMCPError基底クラスのテスト."""

    def test_basic_error(self) -> None:
        """基本的なエラーメッセージを確認."""
        error = GoogleCalendarMCPError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details == {}
        assert error.original_error is None

    def test_error_with_details(self) -> None:
        """詳細情報付きエラーを確認."""
        error = GoogleCalendarMCPError(
            "Test error",
            details={"key1": "value1", "key2": 123},
        )
        error_str = str(error)
        assert "Test error" in error_str
        assert "key1=value1" in error_str
        assert "key2=123" in error_str

    def test_error_with_original_error(self) -> None:
        """元の例外をラップしたエラーを確認."""
        original = ValueError("Original error")
        error = GoogleCalendarMCPError(
            "Wrapper error",
            original_error=original,
        )
        error_str = str(error)
        assert "Wrapper error" in error_str
        assert "ValueError" in error_str
        assert "Original error" in error_str


class TestGoogleCalendarAPIError:
    """GoogleCalendarAPIErrorのテスト."""

    def test_api_error_with_status_code(self) -> None:
        """ステータスコード付きAPIエラーを確認."""
        error = GoogleCalendarAPIError(
            "API error occurred",
            status_code=400,
            error_code="bad_request",
        )
        assert error.status_code == 400
        assert error.error_code == "bad_request"
        assert "400" in str(error)
        assert "bad_request" in str(error)

    def test_api_error_without_codes(self) -> None:
        """コード情報なしのAPIエラーを確認."""
        error = GoogleCalendarAPIError("Generic API error")
        assert error.status_code is None
        assert error.error_code is None


class TestGoogleAuthenticationError:
    """GoogleAuthenticationErrorのテスト."""

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = GoogleAuthenticationError()
        assert "認証に失敗" in error.message
        assert error.status_code == 401
        assert error.error_code == "unauthorized"

    def test_custom_message(self) -> None:
        """カスタムメッセージを確認."""
        error = GoogleAuthenticationError(
            message="Invalid refresh token",
        )
        assert error.message == "Invalid refresh token"
        assert error.status_code == 401


class TestGooglePermissionError:
    """GooglePermissionErrorのテスト."""

    def test_with_resource_info(self) -> None:
        """リソース情報付きエラーを確認."""
        error = GooglePermissionError(
            resource_type="calendar",
            resource_id="cal-123",
        )
        assert error.status_code == 403
        assert error.details["resource_type"] == "calendar"
        assert error.details["resource_id"] == "cal-123"

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = GooglePermissionError()
        assert "アクセス権限がありません" in error.message


class TestGoogleNotFoundError:
    """GoogleNotFoundErrorのテスト."""

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = GoogleNotFoundError()
        assert "見つかりません" in error.message
        assert error.status_code == 404

    def test_with_resource_info(self) -> None:
        """リソース情報付きエラーを確認."""
        error = GoogleNotFoundError(
            resource_type="event",
            resource_id="event-456",
        )
        assert error.details["resource_type"] == "event"
        assert error.details["resource_id"] == "event-456"


class TestGoogleRateLimitError:
    """GoogleRateLimitErrorのテスト."""

    def test_with_retry_after(self) -> None:
        """Retry-After付きエラーを確認."""
        error = GoogleRateLimitError(retry_after=60)
        assert error.status_code == 429
        assert error.error_code == "rate_limited"
        assert error.details["retry_after"] == 60

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = GoogleRateLimitError()
        assert "レート制限" in error.message


class TestGoogleValidationError:
    """GoogleValidationErrorのテスト."""

    def test_with_field(self) -> None:
        """フィールド名付きエラーを確認."""
        error = GoogleValidationError(
            message="Invalid field value",
            field="start_time",
        )
        assert error.status_code == 400
        assert error.error_code == "validation_error"
        assert error.details["field"] == "start_time"

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = GoogleValidationError()
        assert "リクエストパラメータが不正" in error.message


class TestGoogleServerError:
    """GoogleServerErrorのテスト."""

    def test_default_status_code(self) -> None:
        """デフォルトのステータスコードを確認."""
        error = GoogleServerError()
        assert error.status_code == 500
        assert "サーバーエラー" in error.message

    def test_custom_status_code(self) -> None:
        """カスタムステータスコードを確認."""
        error = GoogleServerError(status_code=503)
        assert error.status_code == 503


class TestNetworkError:
    """NetworkErrorのテスト."""

    def test_basic_network_error(self) -> None:
        """基本的なネットワークエラーを確認."""
        error = NetworkError()
        assert "ネットワーク通信" in error.message

    def test_with_original_error(self) -> None:
        """元の例外付きエラーを確認."""
        original = ConnectionError("Connection refused")
        error = NetworkError(
            message="Failed to connect",
            original_error=original,
        )
        assert "ConnectionError" in str(error)


class TestTimeoutError:
    """TimeoutErrorのテスト."""

    def test_with_timeout_seconds(self) -> None:
        """タイムアウト時間付きエラーを確認."""
        error = TimeoutError(timeout_seconds=30.0)
        assert error.details["timeout_seconds"] == 30.0
        assert "タイムアウト" in error.message

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = TimeoutError()
        assert "タイムアウト" in error.message


class TestDataParsingError:
    """DataParsingErrorのテスト."""

    def test_with_field_info(self) -> None:
        """フィールド情報付きエラーを確認."""
        error = DataParsingError(
            message="Failed to parse field",
            field="start.dateTime",
            expected_type="datetime",
            actual_value="invalid-date",
        )
        assert error.details["field"] == "start.dateTime"
        assert error.details["expected_type"] == "datetime"
        assert error.details["actual_value"] == "invalid-date"

    def test_with_long_value(self) -> None:
        """長い値が切り詰められることを確認."""
        long_value = "x" * 200
        error = DataParsingError(
            message="Invalid value",
            actual_value=long_value,
        )
        # 最大100文字まで
        assert len(error.details["actual_value"]) <= 100

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = DataParsingError()
        assert "パース" in error.message


class TestConfigurationError:
    """ConfigurationErrorのテスト."""

    def test_with_config_key(self) -> None:
        """設定キー付きエラーを確認."""
        error = ConfigurationError(
            message="Missing required config",
            config_key="GOOGLE_CLIENT_ID",
        )
        assert error.details["config_key"] == "GOOGLE_CLIENT_ID"

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = ConfigurationError()
        assert "設定の読み込み" in error.message
