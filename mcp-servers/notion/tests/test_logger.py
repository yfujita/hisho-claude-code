"""Tests for logger module.

構造化ログとリクエストロガーの動作をテストします。
"""

import io
import json
import logging

import pytest

from src.logger import (
    ContextLogger,
    RequestLogger,
    StructuredFormatter,
    get_request_logger,
    setup_logger,
)


class TestStructuredFormatter:
    """StructuredFormatterのテスト."""

    def test_plain_format(self) -> None:
        """通常フォーマットでログが出力されることを確認."""
        formatter = StructuredFormatter(use_json=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        assert "INFO" in output
        assert "Test message" in output
        assert "test" in output

    def test_json_format(self) -> None:
        """JSON形式でログが出力されることを確認."""
        formatter = StructuredFormatter(use_json=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        # JSONとしてパース可能か確認
        log_data = json.loads(output)
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["logger"] == "test"
        assert "timestamp" in log_data

    def test_plain_format_with_extra_fields(self) -> None:
        """追加フィールド付きの通常フォーマットを確認."""
        formatter = StructuredFormatter(use_json=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"user_id": "123", "request_id": "req-456"}

        output = formatter.format(record)
        assert "user_id=123" in output
        assert "request_id=req-456" in output

    def test_json_format_with_extra_fields(self) -> None:
        """追加フィールド付きのJSON形式を確認."""
        formatter = StructuredFormatter(use_json=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"user_id": "123", "request_id": "req-456"}

        output = formatter.format(record)
        log_data = json.loads(output)
        assert log_data["user_id"] == "123"
        assert log_data["request_id"] == "req-456"


class TestContextLogger:
    """ContextLoggerのテスト."""

    def test_context_logger(self) -> None:
        """コンテキスト情報が自動的に追加されることを確認."""
        base_logger = logging.getLogger("test_context")
        context_logger = ContextLogger(
            base_logger,
            {"request_id": "req-789", "user_id": "user-123"},
        )

        # processメソッドが正しく動作するか確認
        msg, kwargs = context_logger.process("Test message", {})
        assert "extra_fields" in kwargs["extra"]
        assert kwargs["extra"]["extra_fields"]["request_id"] == "req-789"
        assert kwargs["extra"]["extra_fields"]["user_id"] == "user-123"


class TestRequestLogger:
    """RequestLoggerのテスト."""

    def test_log_request(self) -> None:
        """リクエストログが正しく記録されることを確認."""
        base_logger = logging.getLogger("test_request")
        base_logger.setLevel(logging.DEBUG)

        # メモリ内にログを記録
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter(use_json=False))
        base_logger.addHandler(handler)

        req_logger = RequestLogger(base_logger)
        start_time = req_logger.log_request(
            method="GET",
            url="https://api.example.com/data",
        )

        assert start_time > 0
        log_output = stream.getvalue()
        assert "GET" in log_output
        assert "https://api.example.com/data" in log_output

    def test_log_response_success(self) -> None:
        """成功レスポンスのログを確認."""
        base_logger = logging.getLogger("test_response_success")
        base_logger.setLevel(logging.DEBUG)

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter(use_json=False))
        base_logger.addHandler(handler)

        req_logger = RequestLogger(base_logger)
        start_time = req_logger.log_request("GET", "https://api.example.com/data")
        req_logger.log_response(start_time, 200)

        log_output = stream.getvalue()
        assert "200" in log_output

    def test_log_response_error(self) -> None:
        """エラーレスポンスのログレベルを確認."""
        base_logger = logging.getLogger("test_response_error")
        base_logger.setLevel(logging.DEBUG)

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter(use_json=False))
        base_logger.addHandler(handler)

        req_logger = RequestLogger(base_logger)
        start_time = req_logger.log_request("POST", "https://api.example.com/create")
        req_logger.log_response(start_time, 500, error=Exception("Server error"))

        log_output = stream.getvalue()
        assert "500" in log_output
        assert "ERROR" in log_output

    def test_mask_sensitive_headers(self) -> None:
        """機密情報を含むヘッダーがマスクされることを確認."""
        base_logger = logging.getLogger("test_mask_headers")
        req_logger = RequestLogger(base_logger)

        headers = {
            "Authorization": "Bearer secret_token_1234567890",
            "Content-Type": "application/json",
        }

        masked = req_logger._mask_sensitive_headers(headers)
        assert masked["Authorization"] == "Bear..."
        assert masked["Content-Type"] == "application/json"

    def test_truncate_body(self) -> None:
        """長いボディが切り詰められることを確認."""
        base_logger = logging.getLogger("test_truncate")
        req_logger = RequestLogger(base_logger)

        long_body = "x" * 1000
        truncated = req_logger._truncate_body(long_body, max_length=100)
        assert len(truncated) <= 103  # 100 + "..."
        assert truncated.endswith("...")


class TestSetupLogger:
    """setup_logger関数のテスト."""

    def test_setup_logger_default(self) -> None:
        """デフォルト設定でロガーをセットアップできることを確認."""
        logger = setup_logger("test_setup_default")
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1

    def test_setup_logger_with_level(self) -> None:
        """ログレベルを指定してロガーをセットアップできることを確認."""
        logger = setup_logger("test_setup_level", level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_setup_logger_with_json(self) -> None:
        """JSON形式でロガーをセットアップできることを確認."""
        stream = io.StringIO()
        logger = setup_logger("test_setup_json", level="INFO", use_json=True, stream=stream)

        logger.info("Test message")
        output = stream.getvalue()

        # JSON形式でパース可能か確認
        log_data = json.loads(output.strip())
        assert log_data["message"] == "Test message"
        assert log_data["level"] == "INFO"


class TestGetRequestLogger:
    """get_request_logger関数のテスト."""

    def test_get_request_logger(self) -> None:
        """RequestLoggerを取得できることを確認."""
        base_logger = logging.getLogger("test_get_req_logger")
        req_logger = get_request_logger(base_logger)

        assert isinstance(req_logger, RequestLogger)
        assert req_logger.logger == base_logger
