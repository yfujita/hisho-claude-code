"""Tests for exceptions module.

カスタム例外クラスの動作をテストします。
"""

import pytest

from src.exceptions import (
    CacheError,
    ConfigurationError,
    DataParsingError,
    NetworkError,
    NotionAPIError,
    NotionAuthenticationError,
    NotionConflictError,
    NotionMCPError,
    NotionPermissionError,
    NotionRateLimitError,
    NotionResourceNotFoundError,
    NotionServerError,
    NotionValidationError,
    TimeoutError,
)


class TestNotionMCPError:
    """NotionMCPError基底クラスのテスト."""

    def test_basic_error(self) -> None:
        """基本的なエラーメッセージを確認."""
        error = NotionMCPError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details == {}
        assert error.original_error is None

    def test_error_with_details(self) -> None:
        """詳細情報付きエラーを確認."""
        error = NotionMCPError(
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
        error = NotionMCPError(
            "Wrapper error",
            original_error=original,
        )
        error_str = str(error)
        assert "Wrapper error" in error_str
        assert "ValueError" in error_str
        assert "Original error" in error_str


class TestNotionAPIError:
    """NotionAPIErrorのテスト."""

    def test_api_error_with_status_code(self) -> None:
        """ステータスコード付きAPIエラーを確認."""
        error = NotionAPIError(
            "API error occurred",
            status_code=400,
            error_code="bad_request",
        )
        assert error.status_code == 400
        assert error.error_code == "bad_request"
        assert "400" in str(error)
        assert "bad_request" in str(error)


class TestNotionAuthenticationError:
    """NotionAuthenticationErrorのテスト."""

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = NotionAuthenticationError()
        assert "認証に失敗" in error.message
        assert error.status_code == 401
        assert error.error_code == "unauthorized"

    def test_custom_message(self) -> None:
        """カスタムメッセージを確認."""
        error = NotionAuthenticationError(
            message="Invalid API key provided",
        )
        assert error.message == "Invalid API key provided"
        assert error.status_code == 401


class TestNotionPermissionError:
    """NotionPermissionErrorのテスト."""

    def test_with_resource_info(self) -> None:
        """リソース情報付きエラーを確認."""
        error = NotionPermissionError(
            resource_type="database",
            resource_id="db-123",
        )
        assert error.status_code == 403
        assert error.details["resource_type"] == "database"
        assert error.details["resource_id"] == "db-123"


class TestNotionResourceNotFoundError:
    """NotionResourceNotFoundErrorのテスト."""

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = NotionResourceNotFoundError()
        assert "見つかりません" in error.message
        assert error.status_code == 404

    def test_with_resource_info(self) -> None:
        """リソース情報付きエラーを確認."""
        error = NotionResourceNotFoundError(
            resource_type="page",
            resource_id="page-456",
        )
        assert error.details["resource_type"] == "page"
        assert error.details["resource_id"] == "page-456"


class TestNotionRateLimitError:
    """NotionRateLimitErrorのテスト."""

    def test_with_retry_after(self) -> None:
        """Retry-After付きエラーを確認."""
        error = NotionRateLimitError(retry_after=60)
        assert error.status_code == 429
        assert error.error_code == "rate_limited"
        assert error.details["retry_after"] == 60

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = NotionRateLimitError()
        assert "レート制限" in error.message


class TestNotionConflictError:
    """NotionConflictErrorのテスト."""

    def test_default_values(self) -> None:
        """デフォルト値を確認."""
        error = NotionConflictError()
        assert error.status_code == 409
        assert error.error_code == "conflict_error"
        assert "競合" in error.message


class TestNotionValidationError:
    """NotionValidationErrorのテスト."""

    def test_with_field(self) -> None:
        """フィールド名付きエラーを確認."""
        error = NotionValidationError(
            message="Invalid field value",
            field="due_date",
        )
        assert error.status_code == 400
        assert error.error_code == "validation_error"
        assert error.details["field"] == "due_date"


class TestNotionServerError:
    """NotionServerErrorのテスト."""

    def test_default_status_code(self) -> None:
        """デフォルトのステータスコードを確認."""
        error = NotionServerError()
        assert error.status_code == 500
        assert "サーバーエラー" in error.message

    def test_custom_status_code(self) -> None:
        """カスタムステータスコードを確認."""
        error = NotionServerError(status_code=503)
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


class TestDataParsingError:
    """DataParsingErrorのテスト."""

    def test_with_field_info(self) -> None:
        """フィールド情報付きエラーを確認."""
        error = DataParsingError(
            message="Failed to parse field",
            field="properties.title",
            expected_type="str",
            actual_value=123,
        )
        assert error.details["field"] == "properties.title"
        assert error.details["expected_type"] == "str"
        assert error.details["actual_value"] == "123"

    def test_with_long_value(self) -> None:
        """長い値が切り詰められることを確認."""
        long_value = "x" * 200
        error = DataParsingError(
            message="Invalid value",
            actual_value=long_value,
        )
        # 最大100文字まで
        assert len(error.details["actual_value"]) <= 100


class TestConfigurationError:
    """ConfigurationErrorのテスト."""

    def test_with_config_key(self) -> None:
        """設定キー付きエラーを確認."""
        error = ConfigurationError(
            message="Missing required config",
            config_key="NOTION_API_KEY",
        )
        assert error.details["config_key"] == "NOTION_API_KEY"

    def test_default_message(self) -> None:
        """デフォルトメッセージを確認."""
        error = ConfigurationError()
        assert "設定の読み込み" in error.message


class TestCacheError:
    """CacheErrorのテスト."""

    def test_basic_cache_error(self) -> None:
        """基本的なキャッシュエラーを確認."""
        error = CacheError()
        assert "キャッシュ操作" in error.message

    def test_with_details(self) -> None:
        """詳細情報付きエラーを確認."""
        error = CacheError(
            message="Cache write failed",
            details={"cache_key": "tasks:db-123:false"},
        )
        assert error.details["cache_key"] == "tasks:db-123:false"
