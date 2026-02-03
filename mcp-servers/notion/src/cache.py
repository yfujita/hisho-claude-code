"""Cache management for Notion API results.

このモジュールは、Notion APIの結果をキャッシュし、
不要なAPI呼び出しを削減するための機能を提供します。
"""

import asyncio
import time
from collections import OrderedDict
from typing import Any, Optional


class LRUCacheWithTTL:
    """TTL付きLRUキャッシュ.

    最近最も使用されていない(Least Recently Used)項目を削除するキャッシュで、
    各項目に有効期限(TTL: Time To Live)を設定できます。

    Args:
        capacity: キャッシュの最大容量
        ttl_seconds: 各項目の有効期間（秒）

    Example:
        >>> cache = LRUCacheWithTTL(capacity=100, ttl_seconds=30)
        >>> cache.set("key1", {"data": "value"})
        >>> result = cache.get("key1")
    """

    def __init__(self, capacity: int = 100, ttl_seconds: float = 30.0) -> None:
        """LRUCacheWithTTLを初期化.

        Args:
            capacity: キャッシュの最大容量
            ttl_seconds: 各項目の有効期間（秒）
        """
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """キャッシュから値を取得.

        Args:
            key: キャッシュキー

        Returns:
            Optional[Any]: キャッシュされた値。存在しない場合やTTL切れの場合はNone
        """
        async with self._lock:
            if key not in self._cache:
                return None

            value, timestamp = self._cache[key]
            current_time = time.time()

            # TTLチェック
            if current_time - timestamp > self.ttl_seconds:
                # 期限切れの場合は削除
                del self._cache[key]
                return None

            # LRU: アクセスされた項目を末尾に移動
            self._cache.move_to_end(key)
            return value

    async def set(self, key: str, value: Any) -> None:
        """キャッシュに値を設定.

        Args:
            key: キャッシュキー
            value: キャッシュする値
        """
        async with self._lock:
            current_time = time.time()

            if key in self._cache:
                # 既存のキーを更新
                self._cache.move_to_end(key)
            else:
                # 容量チェック
                if len(self._cache) >= self.capacity:
                    # LRU: 最も古い項目を削除
                    self._cache.popitem(last=False)

            self._cache[key] = (value, current_time)

    async def invalidate(self, key: str) -> None:
        """特定のキーのキャッシュを無効化.

        Args:
            key: 無効化するキャッシュキー
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def invalidate_pattern(self, pattern: str) -> None:
        """パターンに一致するキーのキャッシュを無効化.

        Args:
            pattern: 無効化するキーのパターン（部分一致）
        """
        async with self._lock:
            keys_to_delete = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_delete:
                del self._cache[key]

    async def clear(self) -> None:
        """全てのキャッシュをクリア."""
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        """現在のキャッシュサイズを取得.

        Returns:
            int: キャッシュに保存されている項目数
        """
        async with self._lock:
            return len(self._cache)

    async def cleanup_expired(self) -> int:
        """期限切れの項目をクリーンアップ.

        Returns:
            int: 削除された項目数
        """
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp > self.ttl_seconds
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)


class TaskCache:
    """タスク取得結果のキャッシュ管理.

    Notion APIのタスク取得結果をキャッシュし、
    同じクエリに対する重複リクエストを削減します。

    Args:
        ttl_seconds: キャッシュの有効期間（デフォルト: 30秒）
        capacity: キャッシュの最大容量（デフォルト: 100）

    Example:
        >>> cache = TaskCache(ttl_seconds=30)
        >>> await cache.set_tasks("database_id:false", tasks)
        >>> cached_tasks = await cache.get_tasks("database_id:false")
    """

    def __init__(self, ttl_seconds: float = 30.0, capacity: int = 100) -> None:
        """TaskCacheを初期化.

        Args:
            ttl_seconds: キャッシュの有効期間（秒）
            capacity: キャッシュの最大容量
        """
        self._cache = LRUCacheWithTTL(capacity=capacity, ttl_seconds=ttl_seconds)

    def _make_key(self, database_id: str, include_completed: bool) -> str:
        """キャッシュキーを生成.

        Args:
            database_id: データベースID
            include_completed: 完了済みタスクを含むか

        Returns:
            str: キャッシュキー
        """
        return f"tasks:{database_id}:{include_completed}"

    async def get_tasks(
        self, database_id: str, include_completed: bool = False
    ) -> Optional[list[Any]]:
        """キャッシュからタスク一覧を取得.

        Args:
            database_id: データベースID
            include_completed: 完了済みタスクを含むか

        Returns:
            Optional[list[Any]]: キャッシュされたタスク一覧。存在しない場合はNone
        """
        key = self._make_key(database_id, include_completed)
        return await self._cache.get(key)

    async def set_tasks(
        self, database_id: str, include_completed: bool, tasks: list[Any]
    ) -> None:
        """タスク一覧をキャッシュに保存.

        Args:
            database_id: データベースID
            include_completed: 完了済みタスクを含むか
            tasks: タスク一覧
        """
        key = self._make_key(database_id, include_completed)
        await self._cache.set(key, tasks)

    async def invalidate_database(self, database_id: str) -> None:
        """特定のデータベースのキャッシュを全て無効化.

        タスクが更新・作成された場合に呼び出します。

        Args:
            database_id: 無効化するデータベースID
        """
        await self._cache.invalidate_pattern(f"tasks:{database_id}:")

    async def clear(self) -> None:
        """全てのキャッシュをクリア."""
        await self._cache.clear()
