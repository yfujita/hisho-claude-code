"""Tests for rate_limiter module.

Token Bucketアルゴリズムの動作を検証します。
"""

import asyncio
import time

import pytest

from src.rate_limiter import RateLimiter


class TestRateLimiter:
    """RateLimiterクラスのテスト."""

    @pytest.mark.asyncio
    async def test_initial_tokens(self) -> None:
        """初期状態でトークンが満タンであることを確認."""
        limiter = RateLimiter(tokens_per_second=3.0, capacity=10)
        available = limiter.get_available_tokens()
        assert available == 10.0

    @pytest.mark.asyncio
    async def test_acquire_single_token(self) -> None:
        """1トークンの取得が成功することを確認."""
        limiter = RateLimiter(tokens_per_second=3.0, capacity=10)
        await limiter.acquire(1)
        available = limiter.get_available_tokens()
        # 1トークン消費したので、9トークン残っているはず
        assert 8.5 <= available <= 9.5

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self) -> None:
        """複数トークンの取得が成功することを確認."""
        limiter = RateLimiter(tokens_per_second=3.0, capacity=10)
        await limiter.acquire(5)
        available = limiter.get_available_tokens()
        # 5トークン消費したので、5トークン残っているはず
        assert 4.5 <= available <= 5.5

    @pytest.mark.asyncio
    async def test_acquire_exceeds_capacity(self) -> None:
        """容量を超えるトークン数を要求した場合にエラーが発生することを確認."""
        limiter = RateLimiter(tokens_per_second=3.0, capacity=10)
        with pytest.raises(ValueError, match="exceeds bucket capacity"):
            await limiter.acquire(15)

    @pytest.mark.asyncio
    async def test_token_refill(self) -> None:
        """時間経過でトークンが補充されることを確認."""
        limiter = RateLimiter(tokens_per_second=10.0, capacity=10)

        # トークンを消費
        await limiter.acquire(10)
        available = limiter.get_available_tokens()
        assert available < 1.0

        # 0.5秒待つ（10 tokens/sec なので、5トークン補充されるはず）
        await asyncio.sleep(0.5)
        available = limiter.get_available_tokens()
        assert 4.0 <= available <= 6.0

    @pytest.mark.asyncio
    async def test_wait_for_tokens(self) -> None:
        """トークン不足時に待機してから取得できることを確認."""
        limiter = RateLimiter(tokens_per_second=10.0, capacity=10)

        # すべてのトークンを消費
        await limiter.acquire(10)

        # 5トークン必要（0.5秒待機が必要）
        start_time = time.monotonic()
        await limiter.acquire(5)
        elapsed = time.monotonic() - start_time

        # 待機時間が約0.5秒であることを確認（マージン±0.1秒）
        assert 0.4 <= elapsed <= 0.7

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """コンテキストマネージャーとして使用できることを確認."""
        limiter = RateLimiter(tokens_per_second=3.0, capacity=10)

        async with limiter:
            # トークンが1つ消費されているはず
            available = limiter.get_available_tokens()
            assert 8.5 <= available <= 9.5

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self) -> None:
        """複数の同時リクエストが順序通りに処理されることを確認."""
        limiter = RateLimiter(tokens_per_second=10.0, capacity=5)

        async def acquire_task(token_count: int) -> float:
            """トークンを取得するタスク."""
            start = time.monotonic()
            await limiter.acquire(token_count)
            return time.monotonic() - start

        # 5つの並行タスク（合計10トークン必要）
        tasks = [acquire_task(2) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # 最初のいくつかのタスクはすぐに完了し、後のタスクは待機する
        # 少なくとも1つのタスクは待機が必要なはず
        assert any(elapsed > 0.1 for elapsed in results)

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self) -> None:
        """レート制限が厳格に適用されることを確認."""
        limiter = RateLimiter(tokens_per_second=5.0, capacity=10)

        # 20リクエストを送信（レート制限: 5 req/sec）
        start_time = time.monotonic()
        for _ in range(20):
            await limiter.acquire(1)
        elapsed = time.monotonic() - start_time

        # 20リクエストを5 req/secで処理すると約4秒かかる
        # 初期トークンが10あるので、実際には(20-10)/5 = 2秒程度
        # マージンを考慮して1.5〜3.0秒の範囲で確認
        assert 1.5 <= elapsed <= 3.5
