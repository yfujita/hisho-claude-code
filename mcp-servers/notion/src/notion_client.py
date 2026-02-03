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
from .models import (
    Memo,
    NotionDatabaseQueryResponse,
    NotionPage,
    Task,
    TaskPriority,
    TaskStatus,
)
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

    async def get_task(self, page_id: str) -> Task:
        """タスクを1件取得.

        Args:
            page_id: ページID

        Returns:
            Task: タスクモデル
        """
        page = await self.retrieve_page(page_id)
        return self._parse_task(page)

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

        return self._pages_to_tasks(pages)

    async def search_tasks(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        database_id: Optional[str] = None,
    ) -> list[Task]:
        """タスクを検索.

        Args:
            query: 検索クエリ（タイトルに含まれる文字列）
            status: ステータスフィルタ
            tag: タグフィルタ
            database_id: データベースID

        Returns:
            list[Task]: タスクのリスト
        """
        if database_id is None:
            database_id = self.config.notion_task_database_id

        filter_conditions: dict[str, Any] = {"and": []}

        # タイトル検索
        if query:
            filter_conditions["and"].append({
                "property": self.config.task_prop_title,
                "title": {"contains": query},
            })

        # ステータス検索
        if status:
            filter_conditions["and"].append({
                "property": self.config.task_prop_status,
                "status": {"equals": status},
            })

        # タグ検索
        if tag:
            filter_conditions["and"].append({
                "property": self.config.task_prop_tags,
                "multi_select": {"contains": tag},
            })

        # 条件がない場合は全件取得（制限あり）
        if not filter_conditions["and"]:
            filter_conditions = None

        pages = await self.query_database(
            database_id=database_id,
            filter_conditions=filter_conditions,
        )
        return self._pages_to_tasks(pages)

    def _pages_to_tasks(self, pages: list[NotionPage]) -> list[Task]:
        """ページリストをタスクリストに変換."""
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

    async def append_block_children(
        self, block_id: str, children: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """ブロックに子ブロックを追加（追記）.

        Args:
            block_id: ブロックID（またはページID）
            children: 追加するブロックのリスト

        Returns:
            dict[str, Any]: APIレスポンス
        """
        endpoint = f"blocks/{block_id}/children"
        request_body = {"children": children}

        logger.info(f"Appending blocks to {block_id}")
        return await self._request("PATCH", endpoint, request_body)

    async def update_memo(
        self,
        page_id: str,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        content: Optional[str] = None,
    ) -> dict[str, Any]:
        """メモを更新.

        タイトル、タグの更新、および内容の追記が可能です。

        Args:
            page_id: メモのページID
            title: 新しいタイトル（Noneの場合は更新なし）
            tags: 新しいタグリスト（Noneの場合は更新なし）
            content: 追記する内容（Noneの場合は追記なし）

        Returns:
            dict[str, Any]: 更新後のページ情報（プロパティ更新があった場合）
                             または追記結果（プロパティ更新がなく追記のみの場合）
        """
        # プロパティの更新
        properties: dict[str, Any] = {}

        if title is not None:
            properties[self.config.memo_prop_title] = {
                "type": "title",
                "title": [{"type": "text", "text": {"content": title}}],
            }

        if tags is not None and self.config.memo_prop_tags:
            properties[self.config.memo_prop_tags] = {
                "type": "multi_select",
                "multi_select": [{"name": tag} for tag in tags],
            }

        response = {}
        if properties:
            logger.info(f"Updating memo properties: {page_id}")
            response = await self.update_page(page_id, properties)

        # 内容の追記
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
            await self.append_block_children(page_id, children)
            # プロパティ更新がない場合は追記の結果を返すわけではないが、
            # 便宜上、最後の操作のレスポンスまたは空を返す
            if not response:
                # ページの最新状態を取得して返すのが親切だが、
                # ここでは簡易的に空辞書を返さないようにする
                pass

    async def get_block_children(
        self, block_id: str, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """ブロックの子要素を取得.

        Args:
            block_id: ブロックID
            page_size: 1ページあたりの取得数

        Returns:
            list[dict[str, Any]]: ブロックのリスト
        """
        endpoint = f"blocks/{block_id}/children"
        request_body = {"page_size": page_size}

        all_blocks = []
        has_more = True
        start_cursor = None

        while has_more:
            params = {"page_size": page_size}
            if start_cursor:
                params["start_cursor"] = start_cursor

            # GETリクエストの場合、_requestメソッドのjson_data引数は使えないので修正が必要
            # ただし、httpx.AsyncClient.requestはparams引数を受け取るが、
            # 現在の_request実装はjson_data（body）しか受け取っていない。
            # GETリクエストでクエリパラメータを送るために_requestを修正するか、
            # ここで直接clientを使用するか、URLに埋め込む必要がある。
            # 今回は安全のため、URLにクエリパラメータを埋め込む簡易実装とする（_request経由）
            
            # 注: _requestはメソッドとエンドポイントを受け取る。
            # httpxはparamsをサポートするが、ラッパーがサポートしていない。
            # 簡易的にURLパラメータとして構築する。
            query_string = f"?page_size={page_size}"
            if start_cursor:
                query_string += f"&start_cursor={start_cursor}"
            
            response_data = await self._request("GET", f"{endpoint}{query_string}")
            
            blocks = response_data.get("results", [])
            all_blocks.extend(blocks)
            
            has_more = response_data.get("has_more", False)
            start_cursor = response_data.get("next_cursor")

        logger.info(f"Retrieved {len(all_blocks)} blocks from {block_id}")
        return all_blocks

    async def update_block(
        self, block_id: str, block_type: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        """ブロックを更新.

        Args:
            block_id: ブロックID
            block_type: ブロックタイプ（paragraph, to_do など）
            content: 更新するコンテンツ内容

        Returns:
            dict[str, Any]: APIレスポンス
        """
        endpoint = f"blocks/{block_id}"
        request_body = {block_type: content}

        logger.info(f"Updating block {block_id}")
        return await self._request("PATCH", endpoint, request_body)

    async def add_comment_to_page(
        self, page_id: str, content: str
    ) -> dict[str, Any]:
        """ページにコメントを追加.

        Args:
            page_id: ページID
            content: コメント内容

        Returns:
            dict[str, Any]: APIレスポンス
        """
        endpoint = "comments"
        request_body = {
            "parent": {"page_id": page_id},
            "rich_text": [{"text": {"content": content}}],
        }

        logger.info(f"Adding comment to page {page_id}")
        return await self._request("POST", endpoint, request_body)

    def blocks_to_text(self, blocks: list[dict[str, Any]]) -> str:
        """ブロックのリストをテキスト（Markdown風）に変換.

        Args:
            blocks: ブロックのリスト

        Returns:
            str: テキスト表現
        """
        lines = []
        for block in blocks:
            block_id = block.get("id", "")
            type_ = block.get("type")
            content = block.get(type_, {})
            rich_text = content.get("rich_text", [])
            
            text = ""
            for rt in rich_text:
                plain_text = rt.get("plain_text", "")
                href = rt.get("href")
                if href:
                    text += f"[{plain_text}]({href})"
                else:
                    text += plain_text

            prefix = ""
            suffix = ""
            
            # ブロックIDを表示（デバッグや操作用）
            # 特にTODOアイテムなどは操作のためにIDが必要
            id_str = ""
            
            if type_ == "heading_1":
                prefix = "# "
            elif type_ == "heading_2":
                prefix = "## "
            elif type_ == "heading_3":
                prefix = "### "
            elif type_ == "bulleted_list_item":
                prefix = "- "
            elif type_ == "numbered_list_item":
                prefix = "1. "  # 簡易実装
            elif type_ == "to_do":
                checked = content.get("checked", False)
                prefix = "- [x] " if checked else "- [ ] "
                # TODOアイテムにはIDを付与して操作しやすくする
                id_str = f" [ID: {block_id}]"
            elif type_ == "quote":
                prefix = "> "
            elif type_ == "code":
                language = content.get("language", "text")
                prefix = f"```{language}\n"
                suffix = "\n```"
            
            lines.append(f"{prefix}{text}{id_str}{suffix}")
            
        return "\n".join(lines)

    async def retrieve_page(self, page_id: str) -> NotionPage:
        """ページ情報を取得.

        Args:
            page_id: ページID

        Returns:
            NotionPage: ページモデル
        """
        endpoint = f"pages/{page_id}"
        response = await self._request("GET", endpoint)
        return NotionPage(**response)

    def _parse_memo(self, page: NotionPage) -> Memo:
        """NotionページをMemoモデルに変換.

        Args:
            page: Notionページ

        Returns:
            Memo: メモモデル
        """
        properties = page.properties

        # タイトルの取得
        title_prop_name = self.config.memo_prop_title
        title_prop = properties.get(title_prop_name)
        if not title_prop:
            # プロパティが見つからない場合はデフォルト値またはエラー
            # ここでは安全のためにUntitledとする
            title = "Untitled"
        else:
            title_list = title_prop.get("title", [])
            title = title_list[0]["text"]["content"] if title_list else "Untitled"

        # タグの取得
        tags: list[str] = []
        if self.config.memo_prop_tags:
            tags_prop = properties.get(self.config.memo_prop_tags, {})
            tags_list = tags_prop.get("multi_select", [])
            tags = [tag["name"] for tag in tags_list]

        return Memo(
            id=page.id,
            title=title,
            tags=tags,
            created_time=page.created_time,
            last_edited_time=page.last_edited_time,
            url=page.url,
        )

    async def get_memo(self, page_id: str) -> Memo:
        """メモを1件取得.

        Args:
            page_id: ページID

        Returns:
            Memo: メモモデル
        """
        page = await self.retrieve_page(page_id)
        return self._parse_memo(page)

    async def get_memos(
        self, database_id: Optional[str] = None
    ) -> list[Memo]:
        """メモ一覧を取得.

        Args:
            database_id: データベースID

        Returns:
            list[Memo]: メモのリスト
        """
        if database_id is None:
            database_id = self.config.notion_memo_database_id

        # 作成日時でソート（新しい順）
        sorts = [{"timestamp": "created_time", "direction": "descending"}]

        pages = await self.query_database(
            database_id=database_id,
            sorts=sorts,
        )

        return self._pages_to_memos(pages)

    async def search_memos(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        database_id: Optional[str] = None,
    ) -> list[Memo]:
        """メモを検索.

        Args:
            query: 検索クエリ（タイトルに含まれる文字列）
            tag: タグフィルタ
            database_id: データベースID

        Returns:
            list[Memo]: メモのリスト
        """
        if database_id is None:
            database_id = self.config.notion_memo_database_id

        filter_conditions: dict[str, Any] = {"and": []}

        # タイトル検索
        if query:
            filter_conditions["and"].append({
                "property": self.config.memo_prop_title,
                "title": {"contains": query},
            })

        # タグ検索
        if tag:
            filter_conditions["and"].append({
                "property": self.config.memo_prop_tags,
                "multi_select": {"contains": tag},
            })

        # 条件がない場合は全件取得（制限あり）
        if not filter_conditions["and"]:
            filter_conditions = None

        pages = await self.query_database(
            database_id=database_id,
            filter_conditions=filter_conditions,
        )
        return self._pages_to_memos(pages)

    def _pages_to_memos(self, pages: list[NotionPage]) -> list[Memo]:
        """ページリストをメモリストに変換."""
        memos = []
        for page in pages:
            try:
                memo = self._parse_memo(page)
                memos.append(memo)
            except Exception as e:
                logger.warning(
                    f"Failed to parse memo from page {page.id}: {e}",
                    extra={"extra_fields": {"page_id": page.id, "error": str(e)}},
                )
                continue
        return memos
