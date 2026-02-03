"""Custom exception classes for Notion MCP Server.

このモジュールは、アプリケーション全体で使用するカスタム例外クラスを定義します。
階層的な例外クラスにより、エラーハンドリングが容易になり、
ユーザーフレンドリーなエラーメッセージを提供できます。
"""

from typing import Any, Optional


class NotionMCPError(Exception):
    """Notion MCP Serverの全例外の基底クラス.

    すべてのカスタム例外はこのクラスを継承します。
    共通のエラーメッセージフォーマットとコンテキスト情報を提供します。

    Attributes:
        message: エラーメッセージ
        details: 追加の詳細情報
        original_error: 元の例外（ラップする場合）
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionMCPErrorを初期化.

        Args:
            message: エラーメッセージ
            details: 追加の詳細情報（デバッグやログ用）
            original_error: 元の例外（存在する場合）
        """
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(message)

    def __str__(self) -> str:
        """エラーメッセージを文字列として返す.

        Returns:
            str: フォーマットされたエラーメッセージ
        """
        base_msg = self.message
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg += f" ({details_str})"
        if self.original_error:
            base_msg += f" [Caused by: {type(self.original_error).__name__}: {self.original_error}]"
        return base_msg


# === Notion API関連の例外 ===


class NotionAPIError(NotionMCPError):
    """Notion API呼び出しに関するエラーの基底クラス.

    HTTP通信やAPIレスポンスに関連するエラーを表現します。

    Attributes:
        status_code: HTTPステータスコード
        error_code: Notionのエラーコード
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionAPIErrorを初期化.

        Args:
            message: エラーメッセージ
            status_code: HTTPステータスコード
            error_code: Notionのエラーコード
            details: 追加の詳細情報
            original_error: 元の例外
        """
        self.status_code = status_code
        self.error_code = error_code
        if status_code:
            details = details or {}
            details["status_code"] = status_code
        if error_code:
            details = details or {}
            details["error_code"] = error_code
        super().__init__(message, details, original_error)


class NotionAuthenticationError(NotionAPIError):
    """認証エラー（401 Unauthorized）.

    APIキーが無効または期限切れの場合に発生します。
    """

    def __init__(
        self,
        message: str = "Notion APIの認証に失敗しました。APIキーを確認してください。",
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionAuthenticationErrorを初期化.

        Args:
            message: エラーメッセージ
            details: 追加の詳細情報
            original_error: 元の例外
        """
        super().__init__(
            message=message,
            status_code=401,
            error_code="unauthorized",
            details=details,
            original_error=original_error,
        )


class NotionPermissionError(NotionAPIError):
    """権限エラー（403 Forbidden）.

    リソースへのアクセス権限がない場合に発生します。
    """

    def __init__(
        self,
        message: str = "Notionリソースへのアクセス権限がありません。",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionPermissionErrorを初期化.

        Args:
            message: エラーメッセージ
            resource_type: リソースタイプ（例: "database", "page"）
            resource_id: リソースID
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        super().__init__(
            message=message,
            status_code=403,
            error_code="restricted_resource",
            details=details,
            original_error=original_error,
        )


class NotionResourceNotFoundError(NotionAPIError):
    """リソースが見つからないエラー（404 Not Found）.

    指定されたページやデータベースが存在しない場合に発生します。
    """

    def __init__(
        self,
        message: str = "指定されたNotionリソースが見つかりません。",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionResourceNotFoundErrorを初期化.

        Args:
            message: エラーメッセージ
            resource_type: リソースタイプ
            resource_id: リソースID
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        super().__init__(
            message=message,
            status_code=404,
            error_code="object_not_found",
            details=details,
            original_error=original_error,
        )


class NotionRateLimitError(NotionAPIError):
    """レート制限エラー（429 Too Many Requests）.

    API呼び出しレートが制限を超えた場合に発生します。
    """

    def __init__(
        self,
        message: str = "Notion APIのレート制限に達しました。しばらくお待ちください。",
        retry_after: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionRateLimitErrorを初期化.

        Args:
            message: エラーメッセージ
            retry_after: リトライまでの待機時間（秒）
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message=message,
            status_code=429,
            error_code="rate_limited",
            details=details,
            original_error=original_error,
        )


class NotionConflictError(NotionAPIError):
    """コンフリクトエラー（409 Conflict）.

    リソースの競合状態が発生した場合に発生します。
    """

    def __init__(
        self,
        message: str = "Notionリソースの競合が発生しました。リトライしてください。",
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionConflictErrorを初期化.

        Args:
            message: エラーメッセージ
            details: 追加の詳細情報
            original_error: 元の例外
        """
        super().__init__(
            message=message,
            status_code=409,
            error_code="conflict_error",
            details=details,
            original_error=original_error,
        )


class NotionValidationError(NotionAPIError):
    """バリデーションエラー（400 Bad Request）.

    リクエストパラメータが不正な場合に発生します。
    """

    def __init__(
        self,
        message: str = "リクエストパラメータが不正です。",
        field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionValidationErrorを初期化.

        Args:
            message: エラーメッセージ
            field: エラーが発生したフィールド名
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            status_code=400,
            error_code="validation_error",
            details=details,
            original_error=original_error,
        )


class NotionServerError(NotionAPIError):
    """サーバーエラー（5xx）.

    Notion側のサーバーエラーが発生した場合に発生します。
    """

    def __init__(
        self,
        message: str = "Notion APIでサーバーエラーが発生しました。時間をおいて再度お試しください。",
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NotionServerErrorを初期化.

        Args:
            message: エラーメッセージ
            status_code: HTTPステータスコード
            details: 追加の詳細情報
            original_error: 元の例外
        """
        super().__init__(
            message=message,
            status_code=status_code,
            error_code="internal_server_error",
            details=details,
            original_error=original_error,
        )


# === ネットワーク関連の例外 ===


class NetworkError(NotionMCPError):
    """ネットワーク通信に関するエラー.

    接続タイムアウト、DNS解決失敗などのネットワークレベルのエラーを表現します。
    """

    def __init__(
        self,
        message: str = "ネットワーク通信でエラーが発生しました。",
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """NetworkErrorを初期化.

        Args:
            message: エラーメッセージ
            details: 追加の詳細情報
            original_error: 元の例外
        """
        super().__init__(message, details, original_error)


class TimeoutError(NetworkError):
    """タイムアウトエラー.

    リクエストがタイムアウトした場合に発生します。
    """

    def __init__(
        self,
        message: str = "リクエストがタイムアウトしました。",
        timeout_seconds: Optional[float] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """TimeoutErrorを初期化.

        Args:
            message: エラーメッセージ
            timeout_seconds: タイムアウト時間（秒）
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, details, original_error)


# === データ関連の例外 ===


class DataParsingError(NotionMCPError):
    """データパース時のエラー.

    Notion APIのレスポンスをパースする際にエラーが発生した場合に発生します。
    """

    def __init__(
        self,
        message: str = "データのパースに失敗しました。",
        field: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """DataParsingErrorを初期化.

        Args:
            message: エラーメッセージ
            field: エラーが発生したフィールド名
            expected_type: 期待される型
            actual_value: 実際の値
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if field:
            details["field"] = field
        if expected_type:
            details["expected_type"] = expected_type
        if actual_value is not None:
            details["actual_value"] = str(actual_value)[:100]  # 長すぎる値は切り詰め
        super().__init__(message, details, original_error)


# === 設定関連の例外 ===


class ConfigurationError(NotionMCPError):
    """設定エラー.

    環境変数や設定ファイルの読み込みに失敗した場合に発生します。
    """

    def __init__(
        self,
        message: str = "設定の読み込みに失敗しました。",
        config_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """ConfigurationErrorを初期化.

        Args:
            message: エラーメッセージ
            config_key: 設定キー名
            details: 追加の詳細情報
            original_error: 元の例外
        """
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details, original_error)


# === キャッシュ関連の例外 ===


class CacheError(NotionMCPError):
    """キャッシュ操作に関するエラー.

    キャッシュの読み書きに失敗した場合に発生します。
    """

    def __init__(
        self,
        message: str = "キャッシュ操作でエラーが発生しました。",
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """CacheErrorを初期化.

        Args:
            message: エラーメッセージ
            details: 追加の詳細情報
            original_error: 元の例外
        """
        super().__init__(message, details, original_error)
