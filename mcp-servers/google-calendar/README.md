# Google Calendar MCP Server

Google Calendar APIとMCP（Model Context Protocol）を統合したサーバー実装です。

## 概要

このMCPサーバーは、Claude Code（Claude）がGoogle Calendarと連携し、カレンダーイベントの取得、作成、更新などの操作を行えるようにします。

## Phase 1: 基本構造（現在のバージョン）

Phase 1では、以下の基本構造を実装しています。

### 実装済みコンポーネント

#### 1. 設定管理 (`src/config.py`)
- 環境変数からの設定読み込み
- Google OAuth2認証情報の管理
- レート制限設定

#### 2. データモデル (`src/models.py`)
- `CalendarEvent`: カレンダーイベント
- `EventDateTime`: イベントの日時
- `Attendee`: 出席者情報
- Enumクラス: ステータスや返信状況

#### 3. 例外処理 (`src/exceptions.py`)
- 階層的な例外クラス
- Google Calendar API固有のエラーハンドリング
- ネットワークエラー、データパースエラーなど

#### 4. ロギング (`src/logger.py`)
- 構造化ログ（JSON形式対応）
- リクエスト/レスポンストレーシング
- 機密情報のマスキング

#### 5. レート制限 (`src/rate_limiter.py`)
- Token Bucketアルゴリズム
- Google Calendar APIのレート制限遵守（1.5リクエスト/秒）

## 環境変数

以下の環境変数を`.env`ファイルに設定してください。

```bash
# Google Calendar API設定
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
GOOGLE_ACCESS_TOKEN=your-access-token  # オプション
GOOGLE_CALENDAR_ID=primary  # デフォルト: primary
GOOGLE_CALENDAR_TIMEZONE=Asia/Tokyo  # デフォルト: Asia/Tokyo

# MCPサーバー設定（オプション）
MCP_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## 認証情報の取得方法

Google Calendar APIを使用するには、OAuth2認証情報が必要です。

### 1. Google Cloud Consoleでプロジェクトを作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成
3. Google Calendar APIを有効化

### 2. OAuth2クライアントIDを作成

1. 「認証情報」→「認証情報を作成」→「OAuthクライアントID」
2. アプリケーションの種類: デスクトップアプリ
3. クライアントIDとクライアントシークレットをダウンロード

### 3. リフレッシュトークンを取得

認証フローを実行してリフレッシュトークンを取得します（Phase 2で実装予定）。

## ディレクトリ構造

```
mcp-servers/google-calendar/
├── src/
│   ├── __init__.py
│   ├── config.py          # 設定管理
│   ├── models.py          # データモデル
│   ├── exceptions.py      # 例外クラス
│   ├── logger.py          # ロギング
│   └── rate_limiter.py    # レート制限
├── credentials/
│   └── .gitkeep           # 認証情報保存用（.gitignore対象）
├── tests/
│   └── __init__.py
├── pyproject.toml         # プロジェクト設定
└── README.md              # このファイル
```

## 次のステップ（Phase 2以降）

Phase 2以降で以下の機能を実装予定です。

- Google Calendar APIクライアントの実装
- OAuth2認証フローの実装
- イベント取得・作成・更新・削除のMCPツール
- キャッシュ機構
- テストコード

## ライセンス

MIT
