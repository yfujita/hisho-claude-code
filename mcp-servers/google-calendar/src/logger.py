"""Structured logging configuration for Google Calendar MCP Server.

このモジュールは、構造化ログ（JSON形式）とリクエスト/レスポンスのトレーシングを
サポートするロギング機能を提供します。
"""

import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """構造化ログ（JSON形式）のフォーマッター.

    ログメッセージをJSON形式で出力し、ログ分析ツールでの処理を容易にします。

    Attributes:
        use_json: JSON形式で出力するか（Falseの場合は通常のフォーマット）
    """

    def __init__(self, use_json: bool = False) -> None:
        """StructuredFormatterを初期化.

        Args:
            use_json: JSON形式で出力するか
        """
        self.use_json = use_json
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをフォーマット.

        Args:
            record: ログレコード

        Returns:
            str: フォーマットされたログメッセージ
        """
        if not self.use_json:
            # 通常フォーマット（可読性重視）
            return self._format_plain(record)

        # JSON形式（機械可読性重視）
        return self._format_json(record)

    def _format_plain(self, record: logging.LogRecord) -> str:
        """通常フォーマットでログを出力.

        Args:
            record: ログレコード

        Returns:
            str: フォーマットされたログメッセージ
        """
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        level = record.levelname
        name = record.name
        message = record.getMessage()

        # 基本フォーマット
        log_line = f"{timestamp} - {name} - {level} - {message}"

        # 追加のコンテキスト情報
        if hasattr(record, "extra_fields"):
            extra = record.extra_fields
            extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
            log_line += f" | {extra_str}"

        # 例外情報
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line

    def _format_json(self, record: logging.LogRecord) -> str:
        """JSON形式でログを出力.

        Args:
            record: ログレコード

        Returns:
            str: JSON形式のログメッセージ
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 追加のコンテキスト情報
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # 例外情報
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ContextLogger(logging.LoggerAdapter):
    """コンテキスト情報を付加するロガーアダプター.

    リクエストID、ユーザーIDなどのコンテキスト情報を
    全てのログメッセージに自動的に付加します。

    Example:
        >>> logger = ContextLogger(base_logger, {"request_id": "req-123"})
        >>> logger.info("Processing request")
        # 出力: ... - Processing request | request_id=req-123
    """

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """ログメッセージにコンテキスト情報を追加.

        Args:
            msg: ログメッセージ
            kwargs: ログメソッドに渡されたキーワード引数

        Returns:
            tuple[str, Any]: 処理されたメッセージとキーワード引数
        """
        # extraフィールドにコンテキストを追加
        extra = kwargs.get("extra", {})
        extra["extra_fields"] = {**self.extra, **extra.get("extra_fields", {})}
        kwargs["extra"] = extra
        return msg, kwargs


class RequestLogger:
    """HTTPリクエスト/レスポンスのトレーシングロガー.

    APIリクエストとレスポンスの詳細をログに記録します。
    デバッグやパフォーマンス分析に使用します。
    """

    def __init__(self, logger: logging.Logger) -> None:
        """RequestLoggerを初期化.

        Args:
            logger: ベースロガー
        """
        self.logger = logger

    def log_request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
    ) -> float:
        """リクエスト開始をログに記録.

        Args:
            method: HTTPメソッド
            url: リクエストURL
            headers: リクエストヘッダー（機密情報はマスク済み）
            body: リクエストボディ（JSONなど）

        Returns:
            float: リクエスト開始時刻（monotonic time）
        """
        start_time = time.monotonic()

        log_data = {
            "event": "http_request",
            "method": method,
            "url": self._sanitize_url(url),
        }

        # ヘッダーはAuthorizationなどをマスク
        if headers:
            log_data["headers"] = self._mask_sensitive_headers(headers)

        # ボディは長すぎる場合は切り詰め
        if body:
            log_data["body"] = self._truncate_body(body)

        self.logger.debug(
            f"Request: {method} {url}",
            extra={"extra_fields": log_data},
        )

        return start_time

    def log_response(
        self,
        start_time: float,
        status_code: int,
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """レスポンス受信をログに記録.

        Args:
            start_time: リクエスト開始時刻（log_requestの戻り値）
            status_code: HTTPステータスコード
            headers: レスポンスヘッダー
            body: レスポンスボディ
            error: エラーが発生した場合の例外
        """
        elapsed = time.monotonic() - start_time

        log_data = {
            "event": "http_response",
            "status_code": status_code,
            "elapsed_ms": round(elapsed * 1000, 2),
        }

        # ヘッダー
        if headers:
            log_data["headers"] = dict(headers)

        # ボディは長すぎる場合は切り詰め
        if body:
            log_data["body"] = self._truncate_body(body)

        # エラー情報
        if error:
            log_data["error"] = str(error)

        # ログレベルを決定（エラーコードや実行時間に基づく）
        if error or status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        elif elapsed > 5.0:  # 5秒以上かかった場合
            log_level = logging.WARNING
        else:
            log_level = logging.DEBUG

        self.logger.log(
            log_level,
            f"Response: {status_code} ({elapsed*1000:.0f}ms)",
            extra={"extra_fields": log_data},
        )

    def _sanitize_url(self, url: str) -> str:
        """URLから機密情報を除去.

        Args:
            url: 元のURL

        Returns:
            str: サニタイズされたURL
        """
        # クエリパラメータにトークンなどが含まれている場合は除去
        # 現状はそのまま返す（必要に応じて実装）
        return url

    def _mask_sensitive_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """機密情報を含むヘッダーをマスク.

        Args:
            headers: 元のヘッダー

        Returns:
            dict[str, str]: マスクされたヘッダー
        """
        sensitive_keys = {"authorization", "api-key", "x-api-key", "x-goog-api-key"}
        masked_headers = {}

        for key, value in headers.items():
            if key.lower() in sensitive_keys:
                # 最初の4文字のみ表示
                masked_headers[key] = value[:4] + "..." if len(value) > 4 else "***"
            else:
                masked_headers[key] = value

        return masked_headers

    def _truncate_body(self, body: Any, max_length: int = 500) -> Any:
        """ボディが長すぎる場合は切り詰め.

        Args:
            body: レスポンス/リクエストボディ
            max_length: 最大長（文字数）

        Returns:
            Any: 切り詰められたボディ
        """
        if isinstance(body, str):
            if len(body) > max_length:
                return body[:max_length] + "..."
            return body
        elif isinstance(body, dict):
            # JSON形式の場合
            body_str = json.dumps(body, ensure_ascii=False)
            if len(body_str) > max_length:
                return body_str[:max_length] + "..."
            return body
        else:
            return str(body)[:max_length]


def setup_logger(
    name: str,
    level: str = "INFO",
    use_json: bool = False,
    stream: Any = None,
) -> logging.Logger:
    """ロガーをセットアップ.

    Args:
        name: ロガー名
        level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        use_json: JSON形式で出力するか
        stream: 出力先ストリーム（デフォルト: sys.stderr）

    Returns:
        logging.Logger: 設定されたロガー

    Example:
        >>> logger = setup_logger("my_app", level="DEBUG", use_json=True)
        >>> logger.info("Application started")
    """
    logger = logging.getLogger(name)

    # 既存のハンドラーをクリア（重複防止）
    logger.handlers.clear()

    # ログレベル設定
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # ハンドラー作成
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(log_level)

    # フォーマッター設定
    formatter = StructuredFormatter(use_json=use_json)
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # 伝播を無効化（ルートロガーとの重複を防ぐ）
    logger.propagate = False

    return logger


def get_request_logger(logger: logging.Logger) -> RequestLogger:
    """リクエストロガーを取得.

    Args:
        logger: ベースロガー

    Returns:
        RequestLogger: リクエストロガー

    Example:
        >>> base_logger = setup_logger("my_app")
        >>> req_logger = get_request_logger(base_logger)
        >>> start = req_logger.log_request("GET", "https://www.googleapis.com/calendar/v3/...")
        >>> req_logger.log_response(start, 200)
    """
    return RequestLogger(logger)
