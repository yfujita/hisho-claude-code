"""Notion API Client implementation.

このモジュールは、Notion APIとの通信を行うクライアントを実装しています。
レート制限、エラーハンドリング、リトライ処理を含みます。
"""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from .config import NotionConfig
from .exceptions import (
    DataParsingError,
    NetworkError,
    NotionAPIError,
    NotionAuthenticationError,
    NotionConflictError,
    NotionPermissionError,
    NotionRateLimitError,
    NotionResourceNotFoundError,
    NotionServerError,
    NotionValidationError,
    TimeoutError,
)
from .logger import get_request_logger
from .models import NotionDatabaseQueryResponse, NotionPage, Task, TaskPriority, TaskStatus
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class NotionClient:
    """Notion APIクライアント.

    Notion APIとの通信を行い、タスクの取得・更新・作成を実装します。
    レート制限とエラーハンドリングを含みます。

    Args:
        config: Notion設定
        rate_limiter: レート制限（Noneの場合は自動作成）

    Example:
        >>> config = NotionConfig()
        >>> client = NotionClient(config)
        >>> tasks = await client.get_tasks()
    """

    def __init__(
        self, config: NotionConfig, rate_limiter: Optional[RateLimiter] = None
    ) -> None:
        """NotionClientを初期化.

        Args:
            config: Notion設定
            rate_limiter: レート制限（Noneの場合は設定から自動作成）
        """
        self.config = config
        self.rate_limiter = rate_limiter or RateLimiter(
            tokens_per_second=config.rate_limit_requests_per_second,
            capacity=config.rate_limit_burst,
        )
        self.client = httpx.AsyncClient(
            base_url=config.notion_base_url,
            headers=config.headers,
            timeout=60.0,
        )
        self.request_logger = get_request_logger(logger)

    async def close(self) -> None:
        """HTTPクライアントを閉じる.

        リソースを解放するために、使用後に呼び出す必要があります。
        """
        await self.client.aclose()

    async def __aenter__(self) -> "NotionClient":
        """コンテキストマネージャーの開始（async with用）.

        Returns:
            NotionClient: 自身のインスタンス
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

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Notion APIへのリクエストを実行.

        レート制限、エラーハンドリング、リトライ処理を含みます。

        Args:
            method: HTTPメソッド（GET、POST、PATCHなど）
            endpoint: APIエンドポイント（ベースURLからの相対パス）
            json_data: リクエストボディ（JSON）
            max_retries: 最大リトライ回数

        Returns:
            dict[str, Any]: APIレスポンス（JSON）

        Raises:
            NotionAPIError: API呼び出しが失敗した場合
            httpx.RequestError: ネットワークエラーが発生した場合
        """
        for attempt in range(max_retries):
            try:
                # レート制限を適用
                async with self.rate_limiter:
                    # リクエストログ
                    full_url = f"{self.config.notion_base_url}/{endpoint}"
                    start_time = self.request_logger.log_request(
                        method=method,
                        url=full_url,
                        headers=self.config.headers,
                        body=json_data,
                    )

                    response = await self.client.request(
                        method=method, url=endpoint, json=json_data
                    )

                    # レスポンスログ
                    try:
                        response_body = response.json()
                    except ValueError:
                        response_body = None

                    # レート制限エラー（429）のハンドリング
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning(
                            f"Rate limited. Retrying after {retry_after} seconds...",
                            extra={"extra_fields": {"retry_after": retry_after}},
                        )
                        self.request_logger.log_response(
                            start_time=start_time,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                        )
                        await self.rate_limiter.acquire()  # トークンを待機
                        continue

                    # コンフリクトエラー（409）のハンドリング
                    if response.status_code == 409:
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Conflict error. Retrying in {wait_time} seconds... "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                            self.request_logger.log_response(
                                start_time=start_time,
                                status_code=response.status_code,
                                headers=dict(response.headers),
                            )
                            continue
                        else:
                            self.request_logger.log_response(
                                start_time=start_time,
                                status_code=response.status_code,
                                body=response_body,
                            )
                            self._handle_error_response(response)

                    # サーバーエラー（5xx）のハンドリング
                    if response.status_code >= 500:
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Server error. Retrying in {wait_time} seconds... "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                            self.request_logger.log_response(
                                start_time=start_time,
                                status_code=response.status_code,
                                headers=dict(response.headers),
                            )
                            continue
                        else:
                            self.request_logger.log_response(
                                start_time=start_time,
                                status_code=response.status_code,
                                body=response_body,
                            )
                            self._handle_error_response(response)

                    # クライアントエラー（4xx）のハンドリング
                    if response.status_code >= 400:
                        self.request_logger.log_response(
                            start_time=start_time,
                            status_code=response.status_code,
                            body=response_body,
                        )
                        self._handle_error_response(response)

                    # 成功レスポンス
                    self.request_logger.log_response(
                        start_time=start_time,
                        status_code=response.status_code,
                        body=response_body,
                    )
                    return response_body

            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Timeout error: {e}. Retrying in {wait_time} seconds... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    continue
                else:
                    raise TimeoutError(
                        message="Notion APIへのリクエストがタイムアウトしました",
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
                        message="Notion APIへのネットワーク接続に失敗しました",
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
            NotionAPIError: API呼び出しエラー
        """
        try:
            error_data = response.json()
            status = error_data.get("status", response.status_code)
            code = error_data.get("code", "unknown_error")
            message = error_data.get("message", "An unknown error occurred")
        except ValueError:
            # JSONパースエラーの場合
            raise DataParsingError(
                message=f"Failed to parse error response: {response.text[:200]}",
                details={"status_code": response.status_code},
            )

        # ステータスコードに応じて適切な例外を発生させる
        if status == 401:
            raise NotionAuthenticationError(message=message)
        elif status == 403:
            raise NotionPermissionError(message=message)
        elif status == 404:
            raise NotionResourceNotFoundError(message=message)
        elif status == 409:
            raise NotionConflictError(message=message)
        elif status == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            raise NotionRateLimitError(message=message, retry_after=retry_after)
        elif status >= 500:
            raise NotionServerError(message=message, status_code=status)
        elif status >= 400:
            raise NotionValidationError(message=message)
        else:
            raise NotionAPIError(
                message=message,
                status_code=status,
                error_code=code,
            )

    async def query_database(
        self,
        database_id: Optional[str] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
        sorts: Optional[list[dict[str, Any]]] = None,
        page_size: int = 100,
    ) -> list[NotionPage]:
        """データベースをクエリしてページ一覧を取得.

        ページネーションで全ページを取得します。

        Args:
            database_id: データベースID（Noneの場合は設定から取得）
            filter_conditions: フィルタ条件
            sorts: ソート条件
            page_size: 1ページあたりの結果数

        Returns:
            list[NotionPage]: ページのリスト
        """
        if database_id is None:
            database_id = self.config.notion_task_database_id

        endpoint = f"databases/{database_id}/query"

        # リクエストボディの構築
        request_body: dict[str, Any] = {"page_size": page_size}

        if filter_conditions:
            request_body["filter"] = filter_conditions

        if sorts:
            request_body["sorts"] = sorts

        all_results: list[NotionPage] = []
        has_more = True
        start_cursor: Optional[str] = None

        # ページネーションで全件取得
        while has_more:
            if start_cursor:
                request_body["start_cursor"] = start_cursor

            response_data = await self._request("POST", endpoint, request_body)
            response = NotionDatabaseQueryResponse(**response_data)

            all_results.extend(response.results)
            has_more = response.has_more
            start_cursor = response.next_cursor

            logger.debug(
                f"Retrieved {len(response.results)} pages. "
                f"Total: {len(all_results)}, has_more: {has_more}"
            )

        return all_results

    def _parse_task(self, page: NotionPage) -> Task:
        """NotionページをTaskモデルに変換.

        Args:
            page: Notionページ

        Returns:
            Task: タスクモデル

        Raises:
            DataParsingError: プロパティのパースに失敗した場合
        """
        properties = page.properties

        # タイトルの取得（設定からプロパティ名を取得）
        title_prop_name = self.config.task_prop_title
        title_prop = properties.get(title_prop_name)
        if not title_prop:
            raise DataParsingError(
                message=f"必須プロパティ '{title_prop_name}' が見つかりません",
                field=title_prop_name,
                details={"page_id": page.id},
            )

        title_list = title_prop.get("title", [])
        title = title_list[0]["text"]["content"] if title_list else "Untitled"

        # ステータスの取得（設定からプロパティ名を取得）
        status_prop_name = self.config.task_prop_status
        status_prop = properties.get(status_prop_name, {})
        status_value = status_prop.get("status", {}).get("name", "Not started")
        try:
            status = TaskStatus(status_value)
        except ValueError:
            logger.warning(f"Unknown status: {status_value}, defaulting to Not started")
            status = TaskStatus.NOT_STARTED

        # 優先度の取得（オプショナル、設定からプロパティ名を取得）
        priority: Optional[TaskPriority] = None
        if self.config.task_prop_priority:
            priority_prop = properties.get(self.config.task_prop_priority, {})
            priority_value = priority_prop.get("select", {}).get("name") if priority_prop else None
            if priority_value:
                try:
                    priority = TaskPriority(priority_value)
                except ValueError:
                    logger.warning(f"Unknown priority: {priority_value}")

        # 期限の取得（オプショナル、設定からプロパティ名を取得）
        due_date = None
        if self.config.task_prop_due_date:
            due_date_prop = properties.get(self.config.task_prop_due_date)
            if due_date_prop and due_date_prop.get("date"):
                date_str = due_date_prop["date"].get("start")
                if date_str:
                    # ISO 8601形式の日付文字列をパース（日時情報がある場合は日付部分のみ取得）
                    due_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()

        # タグの取得（オプショナル、設定からプロパティ名を取得）
        tags: list[str] = []
        if self.config.task_prop_tags:
            tags_prop = properties.get(self.config.task_prop_tags, {})
            tags_list = tags_prop.get("multi_select", [])
            tags = [tag["name"] for tag in tags_list]

        return Task(
            id=page.id,
            title=title,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags,
            created_time=page.created_time,
            last_edited_time=page.last_edited_time,
            url=page.url,
        )

    async def get_tasks(
        self, include_completed: bool = False, database_id: Optional[str] = None
    ) -> list[Task]:
        """タスク一覧を取得.

        Args:
            include_completed: 完了済みタスクを含めるか（デフォルト: False）
            database_id: データベースID（Noneの場合は設定から取得）

        Returns:
            list[Task]: タスクのリスト
        """
        # フィルタ条件の構築（設定からプロパティ名を取得）
        filter_conditions = None
        status_prop_name = self.config.task_prop_status
        if not include_completed and status_prop_name:
            # 未完了タスクのみ取得（CompletedとCancelledを除外）
            filter_conditions = {
                "and": [
                    {
                        "property": status_prop_name,
                        "status": {"does_not_equal": TaskStatus.COMPLETED.value},
                    },
                    {
                        "property": status_prop_name,
                        "status": {"does_not_equal": TaskStatus.CANCELLED.value},
                    },
                ]
            }

        # ソート条件（設定されているプロパティのみ使用）
        sorts: list[dict[str, Any]] = []
        if self.config.task_prop_priority:
            sorts.append({"property": self.config.task_prop_priority, "direction": "ascending"})
        if self.config.task_prop_due_date:
            sorts.append({"property": self.config.task_prop_due_date, "direction": "ascending"})
        # 作成日時は常にソートに含める
        sorts.append({"timestamp": "created_time", "direction": "descending"})

        pages = await self.query_database(
            database_id=database_id,
            filter_conditions=filter_conditions,
            sorts=sorts,
        )

        # ページをTaskモデルに変換
        tasks = []
        for page in pages:
            try:
                task = self._parse_task(page)
                tasks.append(task)
            except DataParsingError as e:
                logger.warning(
                    f"Failed to parse task from page {page.id}: {e}",
                    extra={"extra_fields": {"page_id": page.id, "error": str(e)}},
                )
                continue

        logger.info(
            f"Retrieved {len(tasks)} tasks",
            extra={"extra_fields": {"task_count": len(tasks), "database_id": database_id}},
        )
        return tasks

    async def update_page(
        self, page_id: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        """ページのプロパティを更新.

        Args:
            page_id: ページID
            properties: 更新するプロパティ（Notion API形式）

        Returns:
            dict[str, Any]: 更新後のページ情報

        Raises:
            NotionAPIError: API呼び出しが失敗した場合
        """
        endpoint = f"pages/{page_id}"
        request_body = {"properties": properties}

        logger.info(f"Updating page {page_id}")
        return await self._request("PATCH", endpoint, request_body)

    async def update_task_status(self, page_id: str, status: TaskStatus) -> Task:
        """タスクのステータスを更新.

        Args:
            page_id: タスクページID
            status: 新しいステータス

        Returns:
            Task: 更新後のタスク

        Raises:
            NotionAPIError: API呼び出しが失敗した場合
        """
        status_prop_name = self.config.task_prop_status
        properties = {
            status_prop_name: {
                "type": "status",
                "status": {"name": status.value},
            }
        }

        logger.info(f"Updating task status: {page_id} -> {status.value}")
        response = await self.update_page(page_id, properties)

        # 更新後のページ情報をTaskモデルに変換
        page = NotionPage(**response)
        return self._parse_task(page)

    async def update_task(
        self,
        page_id: str,
        title: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        due_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Task:
        """タスクのプロパティを更新.

        Args:
            page_id: タスクページID
            title: タイトル（更新する場合のみ指定）
            status: ステータス（更新する場合のみ指定）
            priority: 優先度（更新する場合のみ指定）
            due_date: 期限（ISO 8601形式、更新する場合のみ指定）
            tags: タグのリスト（更新する場合のみ指定）

        Returns:
            Task: 更新後のタスク

        Raises:
            NotionAPIError: API呼び出しが失敗した場合

        Example:
            >>> task = await client.update_task(
            ...     page_id="xxx",
            ...     status=TaskStatus.COMPLETED,
            ...     priority=TaskPriority.HIGH
            ... )
        """
        properties: dict[str, Any] = {}

        # タイトルの更新（設定からプロパティ名を取得）
        if title is not None:
            properties[self.config.task_prop_title] = {
                "type": "title",
                "title": [{"type": "text", "text": {"content": title}}],
            }

        # ステータスの更新（設定からプロパティ名を取得）
        if status is not None:
            properties[self.config.task_prop_status] = {
                "type": "status",
                "status": {"name": status.value},
            }

        # 優先度の更新（設定でプロパティ名が指定されている場合のみ）
        if priority is not None and self.config.task_prop_priority:
            properties[self.config.task_prop_priority] = {
                "type": "select",
                "select": {"name": priority.value},
            }

        # 期限の更新（設定でプロパティ名が指定されている場合のみ）
        if due_date is not None and self.config.task_prop_due_date:
            properties[self.config.task_prop_due_date] = {
                "type": "date",
                "date": {"start": due_date, "end": None, "time_zone": None},
            }

        # タグの更新（設定でプロパティ名が指定されている場合のみ）
        if tags is not None and self.config.task_prop_tags:
            properties[self.config.task_prop_tags] = {
                "type": "multi_select",
                "multi_select": [{"name": tag} for tag in tags],
            }

        if not properties:
            # 更新する項目がない場合はエラー
            raise ValueError("At least one property must be specified for update")

        logger.info(f"Updating task: {page_id}")
        response = await self.update_page(page_id, properties)

        # 更新後のページ情報をTaskモデルに変換
        page = NotionPage(**response)
        return self._parse_task(page)

    async def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
        children: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """新しいページを作成.

        Args:
            database_id: 親データベースのID
            properties: ページプロパティ（Notion API形式）
            children: ページコンテンツ（ブロック）

        Returns:
            dict[str, Any]: 作成されたページ情報

        Raises:
            NotionAPIError: API呼び出しが失敗した場合
        """
        endpoint = "pages"
        request_body: dict[str, Any] = {
            "parent": {"type": "database_id", "database_id": database_id},
            "properties": properties,
        }

        if children:
            request_body["children"] = children

        logger.info(f"Creating page in database {database_id}")
        return await self._request("POST", endpoint, request_body)

    async def create_task(
        self,
        title: str,
        status: TaskStatus = TaskStatus.NOT_STARTED,
        priority: Optional[TaskPriority] = None,
        due_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
        database_id: Optional[str] = None,
    ) -> Task:
        """新しいタスクを作成.

        Args:
            title: タスクのタイトル
            status: ステータス（デフォルト: Not started）
            priority: 優先度
            due_date: 期限（ISO 8601形式: "2025-02-15"）
            tags: タグのリスト
            database_id: データベースID（Noneの場合は設定から取得）

        Returns:
            Task: 作成されたタスク

        Raises:
            NotionAPIError: API呼び出しが失敗した場合

        Example:
            >>> task = await client.create_task(
            ...     title="新しいタスク",
            ...     status=TaskStatus.NOT_STARTED,
            ...     priority=TaskPriority.HIGH,
            ...     due_date="2025-02-15",
            ...     tags=["urgent", "important"]
            ... )
        """
        if database_id is None:
            database_id = self.config.notion_task_database_id

        # プロパティの構築（設定からプロパティ名を取得）
        properties: dict[str, Any] = {
            self.config.task_prop_title: {
                "type": "title",
                "title": [{"type": "text", "text": {"content": title}}],
            },
            self.config.task_prop_status: {
                "type": "status",
                "status": {"name": status.value},
            },
        }

        # オプショナルなプロパティの追加（設定でプロパティ名が指定されている場合のみ）
        if priority is not None and self.config.task_prop_priority:
            properties[self.config.task_prop_priority] = {
                "type": "select",
                "select": {"name": priority.value},
            }

        if due_date is not None and self.config.task_prop_due_date:
            properties[self.config.task_prop_due_date] = {
                "type": "date",
                "date": {"start": due_date, "end": None, "time_zone": None},
            }

        if tags is not None and self.config.task_prop_tags:
            properties[self.config.task_prop_tags] = {
                "type": "multi_select",
                "multi_select": [{"name": tag} for tag in tags],
            }

        logger.info(f"Creating task: {title}")
        response = await self.create_page(database_id, properties)

        # 作成されたページ情報をTaskモデルに変換
        page = NotionPage(**response)
        return self._parse_task(page)

    async def create_memo(
        self,
        title: str,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        database_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """新しいメモを作成.

        Args:
            title: メモのタイトル
            content: メモの内容（本文）
            tags: タグのリスト
            database_id: データベースID（Noneの場合は設定から取得）

        Returns:
            dict[str, Any]: 作成されたメモページの情報

        Raises:
            NotionAPIError: API呼び出しが失敗した場合

        Example:
            >>> memo = await client.create_memo(
            ...     title="ミーティングメモ",
            ...     content="今日のミーティングの内容...",
            ...     tags=["meeting", "notes"]
            ... )
        """
        if database_id is None:
            database_id = self.config.notion_memo_database_id

        # プロパティの構築（設定からプロパティ名を取得）
        properties: dict[str, Any] = {
            self.config.memo_prop_title: {
                "type": "title",
                "title": [{"type": "text", "text": {"content": title}}],
            }
        }

        # タグがある場合は追加（設定からプロパティ名を取得）
        if tags is not None and self.config.memo_prop_tags:
            properties[self.config.memo_prop_tags] = {
                "type": "multi_select",
                "multi_select": [{"name": tag} for tag in tags],
            }

        # コンテンツをブロックとして追加
        children: Optional[list[dict[str, Any]]] = None
        if content:
            children = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": content}}
                        ]
                    },
                }
            ]

        logger.info(f"Creating memo: {title}")
        return await self.create_page(database_id, properties, children)
