# hisho-claude-code

秘書として振る舞うClaude Codeエージェント

## 概要

このプロジェクトは、Claude Codeを使用してタスク管理とメモ機能を提供する秘書エージェントです。
Notion APIと連携し、タスクの取得・更新・作成、メモの作成などを行います。

## 機能

### Phase 1（MVP）✅ 完了
- ✅ Notionデータベースからタスク一覧を取得
- ✅ レート制限（Token Bucket）実装
- ✅ MCPサーバー基盤構築

### Phase 2（書き込み機能）✅ 完了
- ✅ タスクのステータス更新
- ✅ タスクの新規作成
- ✅ メモの作成
- ✅ キャッシング機能（TTL: 30秒）
- ✅ 新しいMCPツール追加（update_task_status, create_task, create_memo）

## セットアップ

### 前提条件

- Python 3.11以上
- Docker / Docker Compose
- Notion APIのIntegration Token

### Notion APIの準備

1. [Notion Integrations](https://www.notion.so/my-integrations)で新しいインテグレーションを作成
2. Integration Tokenをコピー
3. タスク管理用のNotionデータベースを作成
4. データベースをインテグレーションと共有

### インストール

1. リポジトリをクローン

```bash
git clone <repository-url>
cd hisho-claude-code
```

2. 環境変数を設定

```bash
cp .env.example .env
# .envファイルを編集してNotion API KeyとDatabase IDを設定
```

3. MCPサーバーを起動

```bash
docker-compose up -d
```

4. Claude Codeから秘書エージェントを使用

```bash
./scripts/start_agent.sh
```

## プロジェクト構造

```
hisho-claude-code/
├── CLAUDE.md                    # エージェントの振る舞い定義
├── README.md                    # このファイル
├── .gitignore
├── .env.example
├── .claude/
│   ├── agents/
│   │   └── hisho.json          # 秘書エージェント定義
│   └── mcp-servers/
│       └── claude_mcp_config.json  # MCP設定
├── mcp-servers/
│   └── notion/                 # Notion MCPサーバー
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/                # ソースコード
│       └── tests/              # テスト
├── docker-compose.yml
├── scripts/
│   └── start_agent.sh          # 起動スクリプト
└── work_logs/                  # 作業履歴
```

## 開発

### テストの実行

Dockerを使用したテスト実行（推奨）:

```bash
cd mcp-servers/notion
docker build -f Dockerfile.dev -t hisho-notion-mcp-test .
docker run --rm hisho-notion-mcp-test python -m pytest tests/ -v
```

ローカル環境でのテスト実行:

```bash
cd mcp-servers/notion
pip install -e ".[dev]"
pytest
```

### カバレッジレポート

```bash
pytest --cov=src --cov-report=html
```

### コードフォーマット

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## ライセンス

MIT
