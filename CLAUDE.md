# 秘書エージェント MCP サーバー - プロジェクト定義

このリポジトリは、秘書エージェント（`claude --agent hisho` で起動）が利用する **MCP サーバー**（Notion 連携・Google Calendar 連携）のコードベースです。

- **秘書としてのペルソナ・口調・行動指針・作業ログの書式** は `.claude/agents/hisho.md` に定義されています。エージェントの応対方針を変更する場合はそちらを編集してください。
- 本ファイル（CLAUDE.md）は、**このコードベースを開発・保守する際の規約**と、**MCP ツールの仕様・運用設定のリファレンス**をまとめたものです。

## コーディング規約

### Python
- **PEP 8** に準拠してください
- **型ヒント** を必ず記述してください
- **docstring** を記述してください（Google Style）
- 変数名・関数名は英語で、意味が明確なものを使用してください

### ファイル操作
- 作業ログは `/Users/yfujita/fuji/private/github/hisho-claude-code/work_logs/YYYYMMDD/progress.md` に保存
- 日付ディレクトリが存在しない場合は作成してください
- 作業ログの書式・記録タイミングは `.claude/agents/hisho.md` を参照してください

## MCPツール仕様

秘書エージェントが利用する MCP ツールのパラメータ・レスポンス仕様のリファレンスです。エージェント側での使い分け（どのツールを、どの場面で呼ぶか）は `.claude/agents/hisho.md` を参照してください。

### MCPツール: Notion連携

#### get_tasks
未完了のタスク一覧を取得します。

**パラメータ:**
- `include_completed` (boolean, optional): 完了済みタスクを含めるか（デフォルト: false）

**注意:**
- 結果は30秒間キャッシュされます
- タスクが更新・作成された場合、キャッシュは自動的に無効化されます

#### update_task_status
タスクのステータスを更新します。

**パラメータ:**
- `page_id` (string, required): 更新するタスクのページID
- `status` (string, required): 新しいステータス
  - 選択肢: "バックログ", "未着手", "対応中", "今日やる", "完了"

**注意:**
- ページIDはタスク一覧から取得できます
- 更新後、タスクキャッシュは自動的に無効化されます

#### create_task
新しいタスクをNotionに追加します。

**パラメータ:**
- `title` (string, required): タスクのタイトル
- `status` (string, optional): ステータス（デフォルト: "Not started"）
  - 選択肢: "バックログ", "未着手", "対応中", "今日やる", "完了"
- `priority` (string, optional): 優先度
  - 選択肢: "High", "Medium", "Low"
- `due_date` (string, optional): 期限（ISO 8601形式: "YYYY-MM-DD"）
- `tags` (array of string, optional): タグのリスト

**注意:**
- 作成後、タスクキャッシュは自動的に無効化されます

#### create_memo
メモをNotionに作成します。

**パラメータ:**
- `title` (string, required): メモのタイトル
- `content` (string, optional): メモの内容（本文）
- `tags` (array of string, optional): タグのリスト

**注意:**
- メモはメモ用データベースに作成されます
- contentが長い場合は、レスポンスで省略表示されます

### MCPツール: Google Calendar連携

#### list_calendars
ユーザーがアクセス可能なカレンダー一覧を取得します。

**パラメータ:** なし

**注意:**
- カレンダーIDは他のツールで使用できます
- プライマリカレンダーは `calendar_id` を省略した場合に使用されます

#### get_events
Google Calendarから予定一覧を取得します。

**パラメータ:**
- `calendar_id` (string, optional): カレンダーID。省略時はデフォルトカレンダー（primary）を使用
- `time_min` (string, optional): 取得開始日時（ISO 8601形式）。省略時は現在時刻
- `time_max` (string, optional): 取得終了日時（ISO 8601形式）。省略時はtime_minから7日後
- `max_results` (integer, optional): 最大取得件数（デフォルト: 10）

#### get_event
指定したイベントの詳細情報を取得します。

**パラメータ:**
- `event_id` (string, required): イベントID
- `calendar_id` (string, optional): カレンダーID。省略時はデフォルトカレンダー（primary）を使用

#### create_event
Google Calendarに新しい予定を作成します。

**パラメータ:**
- `summary` (string, required): 予定のタイトル
- `start_time` (string, required): 開始日時（ISO 8601形式）
- `end_time` (string, required): 終了日時（ISO 8601形式）
- `calendar_id` (string, optional): カレンダーID。省略時はデフォルトカレンダー（primary）を使用
- `location` (string, optional): 場所
- `description` (string, optional): 詳細説明

#### update_event
既存の予定を更新します。

**パラメータ:**
- `event_id` (string, required): 更新するイベントのID
- `calendar_id` (string, optional): カレンダーID。省略時はデフォルトカレンダー（primary）を使用
- `summary` (string, optional): 新しいタイトル
- `start_time` (string, optional): 新しい開始日時
- `end_time` (string, optional): 新しい終了日時
- `location` (string, optional): 新しい場所
- `description` (string, optional): 新しい詳細説明

#### get_events_from_multiple_calendars
複数のカレンダーから予定を一括取得します。

**パラメータ:**
- `calendar_ids` (array of string, optional): カレンダーIDのリスト。省略時はすべてのアクセス可能なカレンダーから取得
- `time_min` (string, optional): 取得開始日時（ISO 8601形式）。省略時は現在時刻
- `time_max` (string, optional): 取得終了日時（ISO 8601形式）。省略時はtime_minから7日後
- `max_results_per_calendar` (integer, optional): 各カレンダーからの最大取得件数（デフォルト: 10）

**注意:**
- `calendar_ids` を省略すると、`list_calendars` で取得できるすべてのカレンダーから予定を取得します

## エラーハンドリング

MCPサーバーは階層的なエラーハンドリングを実装しています。エラー種別ごとのリファレンスは以下の通りです。ユーザーへの伝え方（機密情報を伏せる等）は `.claude/agents/hisho.md` を参照してください。

1. **認証エラー（401 Unauthorized）**
   - APIキーが無効または期限切れ
   - 対応: ユーザーに環境変数 `NOTION_API_KEY` の確認を促す
2. **権限エラー（403 Forbidden）**
   - リソースへのアクセス権限がない
   - 対応: データベースIDの確認、Notion側の共有設定を確認
3. **リソース未検出（404 Not Found）**
   - ページやデータベースが存在しない
   - 対応: ページIDやデータベースIDが正しいか確認
4. **レート制限エラー（429 Too Many Requests）**
   - API呼び出しレートが制限を超えた
   - 対応: 自動的にリトライされます（ユーザーへの説明のみ）
5. **バリデーションエラー（400 Bad Request）**
   - リクエストパラメータが不正
   - 対応: パラメータの値を確認し、適切な値を使用
6. **サーバーエラー（5xx）**
   - Notion側のサーバーエラー
   - 対応: 時間をおいて再試行するようユーザーに案内
7. **ネットワークエラー**
   - 接続タイムアウト、DNS解決失敗など
   - 対応: ネットワーク接続を確認するようユーザーに案内

## ロギング

MCPサーバーは構造化ログをサポートしています。

### ログレベルの設定
環境変数 `MCP_LOG_LEVEL` でログレベルを制御できます：
- `DEBUG`: すべてのログを出力（開発・デバッグ用）
- `INFO`: 一般的な情報ログ（デフォルト）
- `WARNING`: 警告以上のログ
- `ERROR`: エラーのみ

### JSON形式ログ
環境変数 `MCP_LOG_JSON=true` を設定すると、JSON形式でログが出力されます。

### リクエストトレーシング
デバッグレベル（`DEBUG`）では、以下の情報が記録されます：
- HTTPリクエスト（メソッド、URL、ヘッダー）
- HTTPレスポンス（ステータスコード、レスポンス時間）
- レート制限の状態
- キャッシュのヒット/ミス

## パフォーマンス最適化

### キャッシュ戦略
- タスク取得結果は30秒間キャッシュされます
- タスクの更新・作成時にキャッシュは自動的に無効化されます
- キャッシュはLRU（Least Recently Used）アルゴリズムで管理されます

### レート制限
- Notion APIのレート制限（3リクエスト/秒）を遵守
- Token Bucketアルゴリズムで制御
- バースト許容（最大10リクエスト）

## 注意事項

- Notion APIのレート制限（3リクエスト/秒）を考慮し、過度なリクエストを避けてください
- セキュリティ上、API KeyやDatabase IDは絶対に外部に漏らさないでください
- エラーメッセージには機密情報（APIキーの全文など）が含まれないよう、自動的にマスクされます
