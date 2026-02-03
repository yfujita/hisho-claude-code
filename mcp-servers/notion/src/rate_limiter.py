"""Rate limiter implementation using Token Bucket algorithm.

このモジュールは、Notion APIのレート制限（3リクエスト/秒）を遵守するために
Token Bucketアルゴリズムを実装しています。
"""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Token Bucketアルゴリズムによるレート制限.

    Notion APIのレート制限（3リクエスト/秒）を守るため、
    トークンバケット方式でリクエストレートを制御します。

    仕様:
        - トークンは一定レート（tokens_per_second）で補充される
        - バケットには最大capacity個のトークンを保持可能
        - リクエスト1回につき1トークンを消費
        - トークンが不足している場合、補充されるまで待機

    Args:
        tokens_per_second: 1秒あたりに補充されるトークン数（デフォルト: 3.0）
        capacity: バケットの最大容量（デフォルト: 10）

    Example:
        >>> limiter = RateLimiter(tokens_per_second=3.0, capacity=10)
        >>> async with limiter:
        ...     # Notion APIリクエストを実行
        ...     response = await client.get(...)
    """

    def __init__(self, tokens_per_second: float = 3.0, capacity: int = 10) -> None:
        """RateLimiterを初期化.

        Args:
            tokens_per_second: 1秒あたりに補充されるトークン数
            capacity: バケットの最大容量（バースト許容数）
        """
        self.tokens_per_second = tokens_per_second
        self.capacity = capacity
        self.tokens = float(capacity)  # 初期状態はフル
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def _refill_tokens(self) -> None:
        """経過時間に基づいてトークンを補充.

        最後の更新時刻からの経過時間に応じて、
        tokens_per_secondの割合でトークンを補充します。
        """
        now = time.monotonic()
        elapsed = now - self.last_update

        # 経過時間に応じてトークンを補充
        self.tokens = min(self.capacity, self.tokens + elapsed * self.tokens_per_second)
        self.last_update = now

    async def acquire(self, tokens: int = 1) -> None:
        """トークンを取得（リクエスト実行の許可を得る）.

        指定された数のトークンを取得します。
        トークンが不足している場合は、補充されるまで待機します。

        Args:
            tokens: 取得するトークン数（デフォルト: 1）

        Raises:
            ValueError: トークン数がバケット容量を超える場合
        """
        if tokens > self.capacity:
            raise ValueError(
                f"Requested tokens ({tokens}) exceeds bucket capacity ({self.capacity})"
            )

        async with self._lock:
            while True:
                # トークンを補充
                await self._refill_tokens()

                # トークンが十分にある場合、消費して終了
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # トークン不足の場合、必要なトークンが補充されるまでの時間を計算
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.tokens_per_second

                # 待機時間を考慮してトークンを補充
                await asyncio.sleep(wait_time)

    async def __aenter__(self) -> "RateLimiter":
        """コンテキストマネージャーの開始（async with用）.

        Returns:
            RateLimiter: 自身のインスタンス
        """
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """コンテキストマネージャーの終了（async with用）.

        Args:
            exc_type: 例外の型
            exc_val: 例外の値
            exc_tb: トレースバック
        """
        # トークン取得は __aenter__ で完了しているため、ここでは何もしない
        pass

    def get_available_tokens(self) -> float:
        """現在利用可能なトークン数を取得（デバッグ用）.

        注意: この値は参考値であり、次の瞬間には変わる可能性があります。

        Returns:
            float: 現在のトークン数
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.tokens_per_second)
