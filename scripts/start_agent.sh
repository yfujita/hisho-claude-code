#!/bin/bash

# 秘書エージェント起動スクリプト
# MCPサーバーの起動確認を行い、Claude Codeから秘書エージェントを呼び出します。

set -euo pipefail

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# プロジェクトルートディレクトリ（このスクリプトの親ディレクトリ）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== 秘書エージェント起動スクリプト ===${NC}\n"

# 1. .envファイルの存在確認
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${RED}エラー: .envファイルが見つかりません${NC}"
    echo "以下のコマンドで.envファイルを作成してください："
    echo "  cp .env.example .env"
    echo "  # .envファイルを編集してNotion API KeyとDatabase IDを設定"
    exit 1
fi

echo -e "${GREEN}✓${NC} .envファイルが存在します"

# 2. Docker Composeの起動確認
echo -e "\n${YELLOW}MCPサーバーの起動状態を確認しています...${NC}"

cd "$PROJECT_ROOT"

if ! docker-compose ps | grep -q "hisho-notion-mcp"; then
    echo -e "${YELLOW}MCPサーバーが起動していません。起動します...${NC}"
    docker-compose up -d

    # 起動を待つ
    echo -e "${YELLOW}MCPサーバーの起動を待っています（最大30秒）...${NC}"
    for i in {1..30}; do
        if docker-compose ps | grep -q "hisho-notion-mcp.*Up"; then
            echo -e "${GREEN}✓${NC} MCPサーバーが起動しました"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
else
    # 既に起動している場合
    if docker-compose ps | grep -q "hisho-notion-mcp.*Up"; then
        echo -e "${GREEN}✓${NC} MCPサーバーは既に起動しています"
    else
        echo -e "${YELLOW}MCPサーバーが停止しています。再起動します...${NC}"
        docker-compose restart notion-mcp
        sleep 3
    fi
fi

# 3. MCPサーバーのログを確認（エラーチェック）
echo -e "\n${YELLOW}MCPサーバーのログを確認しています...${NC}"
if docker-compose logs --tail=10 notion-mcp | grep -qi "error\|exception\|failed"; then
    echo -e "${RED}警告: MCPサーバーのログにエラーが検出されました${NC}"
    echo "以下のコマンドでログを確認してください："
    echo "  docker-compose logs -f notion-mcp"
    echo ""
    read -p "続行しますか？ (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} MCPサーバーは正常に動作しています"
fi

# 4. Claude Codeの起動案内
echo -e "\n${GREEN}=== セットアップ完了 ===${NC}"
echo ""
echo "秘書エージェントを使用するには、以下のコマンドを実行してください："
echo ""
echo -e "  ${YELLOW}claude-code --agent hisho${NC}"
echo ""
echo "または、Claude Codeを起動後、エージェントを選択してください。"
echo ""
echo "MCPサーバーを停止するには："
echo -e "  ${YELLOW}docker-compose stop${NC}"
echo ""
