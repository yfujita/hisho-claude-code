# Notion MCP Server

hisho-claude-code プロジェクト用のNotion MCPサーバー

## 概要

このMCPサーバーは、Notion APIと連携してタスク管理とメモ機能を提供します。
Fast MCP（mcp パッケージ）を使用して実装されており、Claude Codeから利用できます。

## 機能

### Phase 1-3（実装完了）
- ✅ タスク一覧の取得（未完了/完了済み）
- ✅ タスクのステータス更新
- ✅ タスクの新規作成
- ✅ メモの作成
- ✅ レート制限（3 req/sec）の実装
- ✅ LRUキャッシュ（TTL付き）
- ✅ エラーハンドリングとリトライ処理
- ✅ 階層的な例外クラス
- ✅ 構造化ログ（JSON形式対応）
- ✅ リクエスト/レスポンスのトレーシング
- ✅ 包括的なテスト（84テスト、カバレッジ44%）

### 提供ツール

#### 1. get_tasks
未完了のタスク一覧を取得します。

**パラメータ:**
- `include_completed` (boolean, optional): 完了済みタスクを含めるか（デフォルト: false）

#### 2. update_task_status
タスクのステータスを更新します。

**パラメータ:**
- `page_id` (string, required): 更新するタスクのページID
- `status` (string, required): 新しいステータス（"未着手", "今日やる", "対応中", "バックログ", "完了 🙌", "キャンセル"）

#### 3. create_task
新しいタスクを作成します。

**パラメータ:**
- `title` (string, required): タスクのタイトル
- `status` (string, optional): ステータス
- `priority` (string, optional): 優先度（"High", "Medium", "Low"）
- `due_date` (string, optional): 期限（ISO 8601形式: "YYYY-MM-DD"）
- `tags` (array of string, optional): タグのリスト

#### 4. create_memo
メモを作成します。

**パラメータ:**
- `title` (string, required): メモのタイトル
- `content` (string, optional): メモの内容
- `tags` (array of string, optional): タグのリスト

## 開発環境のセットアップ

### 1. 依存関係のインストール

```bash
cd mcp-servers/notion
pip install mcp httpx pydantic pydantic-settings python-dotenv
pip install pytest pytest-asyncio pytest-cov  # 開発用
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成：

```bash
# 必須
NOTION_API_KEY=secret_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
NOTION_TASK_DATABASE_ID=your-task-database-id-here
NOTION_MEMO_DATABASE_ID=your-memo-database-id-here

# オプション（ログ設定）
MCP_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
MCP_LOG_JSON=false          # JSON形式ログを有効化

# オプション（プロパティ名のカスタマイズ）
TASK_PROP_TITLE=Name
TASK_PROP_STATUS=ステータス
TASK_PROP_PRIORITY=優先度
TASK_PROP_DUE_DATE=期限
TASK_PROP_TAGS=タグ
```

### 3. テストの実行

```bash
# 基本的なテスト
pytest

# カバレッジ付きテスト
pytest --cov=src --cov-report=term-missing

# HTMLカバレッジレポート
pytest --cov=src --cov-report=html
open htmlcov/index.html

# 特定のテストファイルのみ実行
pytest tests/test_config.py tests/test_models.py -v
```

### 4. リンターの実行

```bash
ruff check src tests
```

## Docker環境での実行

プロジェクトルートで以下のコマンドを実行：

```bash
docker-compose up -d
```

## アーキテクチャ

### モジュール構成

```
src/
├── __init__.py           # パッケージ初期化
├── main.py               # MCPサーバーのエントリーポイント
├── config.py             # 設定管理（Pydantic Settings）
├── models.py             # Pydanticモデル定義
├── exceptions.py         # カスタム例外クラス
├── logger.py             # 構造化ログとリクエストロガー
├── rate_limiter.py       # レート制限（Token Bucket）
├── cache.py              # LRUキャッシュ（TTL付き）
└── notion_client.py      # Notion APIクライアント

tests/
├── conftest.py           # テスト共通設定
├── test_config.py        # 設定のテスト
├── test_models.py        # モデルのテスト
├── test_exceptions.py    # 例外クラスのテスト
├── test_logger.py        # ロガーのテスト
├── test_rate_limiter.py  # レート制限のテスト
├── test_cache.py         # キャッシュのテスト
└── test_notion_client.py # APIクライアントのテスト
```

### レート制限

Notion APIのレート制限（3リクエスト/秒）を遵守するため、Token Bucketアルゴリズムを実装しています。

- **トークン補充レート**: 3 tokens/sec
- **バケット容量**: 10 tokens（バースト許容）
- **自動待機**: トークン不足時は自動的に待機

### キャッシュ戦略

タスク取得結果をキャッシュして不要なAPI呼び出しを削減します。

- **アルゴリズム**: LRU（Least Recently Used）
- **TTL**: 30秒
- **自動無効化**: タスクの更新・作成時に自動的にキャッシュをクリア
- **容量**: 100エントリ

### エラーハンドリング

階層的な例外クラスで詳細なエラー情報を提供します。

#### 例外クラス階層
```
NotionMCPError (基底クラス)
├── NotionAPIError (API関連の基底)
│   ├── NotionAuthenticationError (401)
│   ├── NotionPermissionError (403)
│   ├── NotionResourceNotFoundError (404)
│   ├── NotionRateLimitError (429)
│   ├── NotionConflictError (409)
│   ├── NotionValidationError (400)
│   └── NotionServerError (5xx)
├── NetworkError
│   └── TimeoutError
├── DataParsingError
├── ConfigurationError
└── CacheError
```

#### リトライ処理
- **429 Too Many Requests**: Retry-Afterヘッダーを尊重
- **409 Conflict**: Exponential Backoff（最大3回）
- **5xx Server Error**: Exponential Backoff（最大3回）
- **Timeout**: Exponential Backoff（最大3回）

### ロギング

構造化ログとリクエストトレーシングをサポートします。

#### ログレベル
環境変数 `MCP_LOG_LEVEL` で制御：
- `DEBUG`: すべてのログを出力（リクエスト/レスポンスの詳細含む）
- `INFO`: 一般的な情報ログ（デフォルト）
- `WARNING`: 警告以上のログ
- `ERROR`: エラーのみ

#### JSON形式ログ
環境変数 `MCP_LOG_JSON=true` を設定すると、JSON形式でログが出力されます。
ログ分析ツールでの処理が容易になります。

#### リクエストトレーシング
DEBUGレベルで以下の情報を記録：
- HTTPリクエスト（メソッド、URL、ヘッダー）
- HTTPレスポンス（ステータスコード、レスポンス時間）
- 機密情報の自動マスク（Authorizationヘッダーなど）

## テスト

### テストカバレッジ

```
Name                   Coverage
----------------------------------
src/cache.py          100.00%
src/config.py         100.00%
src/exceptions.py     100.00%
src/logger.py          85.58%
src/models.py         100.00%
src/rate_limiter.py   100.00%
----------------------------------
Total (tested modules) 97.5%
```

84個のテストで主要モジュールをカバーしています。

### テストの実行

```bash
# すべてのテスト
pytest -v

# カバレッジ付き
pytest --cov=src --cov-report=term-missing

# 特定のモジュールのみ
pytest tests/test_config.py -v
```

## トラブルシューティング

### よくあるエラー

#### 1. 認証エラー（401 Unauthorized）
```
NotionAuthenticationError: Notion APIの認証に失敗しました
```

**対処方法:**
- `.env` ファイルの `NOTION_API_KEY` を確認
- Notionの設定から新しいAPIキーを取得

#### 2. 権限エラー（403 Forbidden）
```
NotionPermissionError: Notionリソースへのアクセス権限がありません
```

**対処方法:**
- データベースがインテグレーションに共有されているか確認
- データベースIDが正しいか確認

#### 3. レート制限エラー（429 Too Many Requests）
```
NotionRateLimitError: Notion APIのレート制限に達しました
```

**対処方法:**
- 自動的にリトライされます
- 過度な連続リクエストを避ける

#### 4. ネットワークエラー
```
NetworkError: Notion APIへのネットワーク接続に失敗しました
```

**対処方法:**
- インターネット接続を確認
- ファイアウォール設定を確認

## パフォーマンス

### レスポンス時間

- **キャッシュヒット時**: < 1ms
- **キャッシュミス時**: 200-500ms（Notion APIの応答時間に依存）

### スループット

- **レート制限**: 3リクエスト/秒（Notion APIの制限）
- **バースト**: 最大10リクエスト（キャッシュフル時）

## ライセンス

MIT
