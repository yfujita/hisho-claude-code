"""Tests for cache module.

キャッシュ機能のテストを実装します。
"""

import asyncio

import pytest

from src.cache import LRUCacheWithTTL, TaskCache


class TestLRUCacheWithTTL:
    """LRUCacheWithTTLクラスのテスト."""

    @pytest.mark.asyncio
    async def test_basic_set_get(self) -> None:
        """基本的なset/get操作が正しく動作することを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self) -> None:
        """存在しないキーを取得した場合にNoneが返されることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self) -> None:
        """TTL切れの項目が正しく削除されることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=0.1)

        await cache.set("key1", "value1")

        # 0.15秒待機（TTL: 0.1秒）
        await asyncio.sleep(0.15)

        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self) -> None:
        """容量超過時にLRUアルゴリズムで項目が削除されることを確認."""
        cache = LRUCacheWithTTL(capacity=3, ttl_seconds=60)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # key1にアクセス（末尾に移動）
        await cache.get("key1")

        # key4を追加（key2が削除される）
        await cache.set("key4", "value4")

        # key2は削除され、key1とkey3は残っている
        assert await cache.get("key2") is None
        assert await cache.get("key1") == "value1"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_update_existing_key(self) -> None:
        """既存のキーを更新できることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        await cache.set("key1", "value1")
        await cache.set("key1", "value2")

        result = await cache.get("key1")

        assert result == "value2"

    @pytest.mark.asyncio
    async def test_invalidate(self) -> None:
        """特定のキーを無効化できることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        await cache.set("key1", "value1")
        await cache.invalidate("key1")

        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self) -> None:
        """パターンに一致するキーを無効化できることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        await cache.set("tasks:db1:true", "value1")
        await cache.set("tasks:db1:false", "value2")
        await cache.set("tasks:db2:true", "value3")

        await cache.invalidate_pattern("db1")

        # db1を含むキーは削除される
        assert await cache.get("tasks:db1:true") is None
        assert await cache.get("tasks:db1:false") is None
        # db2を含むキーは残る
        assert await cache.get("tasks:db2:true") == "value3"

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """全てのキャッシュをクリアできることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert await cache.size() == 0
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_size(self) -> None:
        """キャッシュサイズが正しく取得できることを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=60)

        assert await cache.size() == 0

        await cache.set("key1", "value1")
        assert await cache.size() == 1

        await cache.set("key2", "value2")
        assert await cache.size() == 2

        await cache.invalidate("key1")
        assert await cache.size() == 1

    @pytest.mark.asyncio
    async def test_cleanup_expired(self) -> None:
        """期限切れ項目のクリーンアップが正しく動作することを確認."""
        cache = LRUCacheWithTTL(capacity=10, ttl_seconds=0.1)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # 0.15秒待機
        await asyncio.sleep(0.15)

        # 新しい項目を追加
        await cache.set("key3", "value3")

        # クリーンアップ実行
        expired_count = await cache.cleanup_expired()

        # key1とkey2が期限切れで削除される
        assert expired_count == 2
        assert await cache.size() == 1
        assert await cache.get("key3") == "value3"


class TestTaskCache:
    """TaskCacheクラスのテスト."""

    @pytest.mark.asyncio
    async def test_set_and_get_tasks(self) -> None:
        """タスクの保存と取得が正しく動作することを確認."""
        cache = TaskCache(ttl_seconds=60)

        tasks = [{"id": "1", "title": "Task 1"}, {"id": "2", "title": "Task 2"}]

        await cache.set_tasks("database-id", False, tasks)
        result = await cache.get_tasks("database-id", False)

        assert result == tasks

    @pytest.mark.asyncio
    async def test_get_nonexistent_tasks(self) -> None:
        """存在しないタスクを取得した場合にNoneが返されることを確認."""
        cache = TaskCache(ttl_seconds=60)

        result = await cache.get_tasks("database-id", False)

        assert result is None

    @pytest.mark.asyncio
    async def test_different_cache_keys(self) -> None:
        """異なるキャッシュキーが独立して動作することを確認."""
        cache = TaskCache(ttl_seconds=60)

        tasks1 = [{"id": "1", "title": "Task 1"}]
        tasks2 = [{"id": "2", "title": "Task 2"}]

        await cache.set_tasks("database-id", False, tasks1)
        await cache.set_tasks("database-id", True, tasks2)

        result1 = await cache.get_tasks("database-id", False)
        result2 = await cache.get_tasks("database-id", True)

        assert result1 == tasks1
        assert result2 == tasks2

    @pytest.mark.asyncio
    async def test_invalidate_database(self) -> None:
        """データベース単位でキャッシュを無効化できることを確認."""
        cache = TaskCache(ttl_seconds=60)

        tasks1 = [{"id": "1", "title": "Task 1"}]
        tasks2 = [{"id": "2", "title": "Task 2"}]

        await cache.set_tasks("database-id-1", False, tasks1)
        await cache.set_tasks("database-id-1", True, tasks1)
        await cache.set_tasks("database-id-2", False, tasks2)

        # database-id-1のキャッシュを無効化
        await cache.invalidate_database("database-id-1")

        # database-id-1のキャッシュは削除される
        assert await cache.get_tasks("database-id-1", False) is None
        assert await cache.get_tasks("database-id-1", True) is None

        # database-id-2のキャッシュは残る
        assert await cache.get_tasks("database-id-2", False) == tasks2

    @pytest.mark.asyncio
    async def test_clear_all(self) -> None:
        """全てのキャッシュをクリアできることを確認."""
        cache = TaskCache(ttl_seconds=60)

        tasks1 = [{"id": "1", "title": "Task 1"}]
        tasks2 = [{"id": "2", "title": "Task 2"}]

        await cache.set_tasks("database-id-1", False, tasks1)
        await cache.set_tasks("database-id-2", False, tasks2)

        await cache.clear()

        assert await cache.get_tasks("database-id-1", False) is None
        assert await cache.get_tasks("database-id-2", False) is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self) -> None:
        """TTL切れでキャッシュが無効化されることを確認."""
        cache = TaskCache(ttl_seconds=0.1)

        tasks = [{"id": "1", "title": "Task 1"}]

        await cache.set_tasks("database-id", False, tasks)

        # 0.15秒待機
        await asyncio.sleep(0.15)

        result = await cache.get_tasks("database-id", False)

        assert result is None
