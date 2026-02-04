# マルチステージビルド - ビルドステージ
FROM python:3.11-slim as builder

WORKDIR /build

# システムパッケージの更新と必要なツールのインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 依存関係のみをインストール（パッケージ自体はインストールしない）
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "mcp>=0.9.0" \
    "httpx>=0.27.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "python-dotenv>=1.0.0" \
    "google-api-python-client>=2.100.0" \
    "google-auth-httplib2>=0.2.0" \
    "google-auth-oauthlib>=1.2.0"

# 実行ステージ
FROM python:3.11-slim

# 非rootユーザーの作成
RUN useradd -m -u 1000 -s /bin/bash mcp && \
    mkdir -p /app /app/credentials && \
    chown -R mcp:mcp /app

WORKDIR /app

# ビルドステージから依存関係をコピー
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# アプリケーションコードをコピー
COPY --chown=mcp:mcp src/ ./src/

# 非rootユーザーに切り替え
USER mcp

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# MCPサーバーを起動
CMD ["python", "-m", "src.main"]
