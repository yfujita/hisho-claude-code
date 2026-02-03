# Notion API リファレンス

Notion MCP サーバー実装のための Notion API 利用ガイド

**API バージョン**: 2025-09-03  
**最終更新日**: 2026-02-03

## 目次

- [認証方法](#認証方法)
- [主要なエンドポイント](#主要なエンドポイント)
- [リクエスト/レスポンス形式](#リクエストレスポンス形式)
- [プロパティ型とデータ構造](#プロパティ型とデータ構造)
- [レート制限](#レート制限)
- [エラーハンドリング](#エラーハンドリング)
- [実装例（Python + httpx）](#実装例python--httpx)

---

## 認証方法

### Integration Token の取得

#### 内部インテグレーション（Internal Integration）の場合

1. Notion の [My integrations](https://www.notion.so/my-integrations) ページにアクセス
2. "New integration" をクリックして新しいインテグレーションを作成
3. インテグレーション名、ワークスペースを設定
4. "Submit" をクリックして作成完了
5. "Secrets" タブから Integration Token（`secret_XXX...` 形式）をコピー

#### 必要な権限設定

インテグレーション作成時に以下の権限を設定します：

- **Read content**: データベースやページの読み取り
- **Update content**: ページのプロパティ更新
- **Insert content**: 新規ページの作成

#### ページへのアクセス許可

インテグレーションがページやデータベースにアクセスするには、明示的に共有が必要です：

1. 対象のページまたはデータベースを開く
2. 右上の "•••" メニューをクリック
3. "Add connections" を選択
4. 作成したインテグレーションを検索して選択

### API キーの使用方法

#### 環境変数での管理（推奨）

```bash
export NOTION_API_KEY="secret_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

#### セキュリティのベストプラクティス

- ❌ ソースコードに直接トークンを記述しない
- ❌ バージョン管理システムにコミットしない
- ✅ 環境変数または秘密管理システム（Vault、AWS Secrets Manager など）を使用
- ✅ トークンは定期的にローテーションする

---

## 主要なエンドポイント

### 1. データベースクエリ（Query a database）

**⚠️ 注意**: このエンドポイントは API バージョン 2025-09-03 で非推奨となりました。新しい "Query a data source" エンドポイントの使用が推奨されます。

#### エンドポイント

```
POST https://api.notion.com/v1/databases/{database_id}/query
```

#### リクエスト例

```json
{
  "filter": {
    "and": [
      {
        "property": "Status",
        "status": {
          "equals": "In Progress"
        }
      },
      {
        "property": "Priority",
        "select": {
          "equals": "High"
        }
      }
    ]
  },
  "sorts": [
    {
      "property": "Due Date",
      "direction": "ascending"
    },
    {
      "timestamp": "created_time",
      "direction": "descending"
    }
  ],
  "start_cursor": null,
  "page_size": 100
}
```

#### レスポンス例

```json
{
  "object": "list",
  "results": [
    {
      "object": "page",
      "id": "page-id-1",
      "created_time": "2025-01-15T10:00:00.000Z",
      "last_edited_time": "2025-01-20T14:30:00.000Z",
      "properties": {
        "Title": {
          "id": "title",
          "type": "title",
          "title": [
            {
              "type": "text",
              "text": {
                "content": "タスク1"
              }
            }
          ]
        },
        "Status": {
          "id": "status",
          "type": "status",
          "status": {
            "name": "In Progress",
            "color": "blue"
          }
        }
      }
    }
  ],
  "next_cursor": "cursor-string-here",
  "has_more": true
}
```

### 2. ページ作成（Create a page）

#### エンドポイント

```
POST https://api.notion.com/v1/pages
```

#### リクエスト例（データベースにページを作成）

```json
{
  "parent": {
    "type": "database_id",
    "database_id": "database-id-here"
  },
  "properties": {
    "Title": {
      "type": "title",
      "title": [
        {
          "type": "text",
          "text": {
            "content": "新しいタスク"
          }
        }
      ]
    },
    "Status": {
      "type": "status",
      "status": {
        "name": "Not started"
      }
    },
    "Due Date": {
      "type": "date",
      "date": {
        "start": "2025-02-15",
        "end": null,
        "time_zone": null
      }
    }
  }
}
```

#### レスポンス例

```json
{
  "object": "page",
  "id": "new-page-id",
  "created_time": "2025-02-03T10:00:00.000Z",
  "last_edited_time": "2025-02-03T10:00:00.000Z",
  "properties": {
    "Title": {
      "id": "title",
      "type": "title",
      "title": [
        {
          "type": "text",
          "text": {
            "content": "新しいタスク"
          }
        }
      ]
    },
    "Status": {
      "id": "status",
      "type": "status",
      "status": {
        "name": "Not started",
        "color": "default"
      }
    }
  },
  "url": "https://www.notion.so/new-page-id"
}
```

### 3. ページ更新（Update page properties）

#### エンドポイント

```
PATCH https://api.notion.com/v1/pages/{page_id}
```

#### リクエスト例（タスクのステータス更新）

```json
{
  "properties": {
    "Status": {
      "type": "status",
      "status": {
        "name": "Completed"
      }
    },
    "Completed Date": {
      "type": "date",
      "date": {
        "start": "2025-02-03",
        "end": null,
        "time_zone": null
      }
    }
  }
}
```

#### レスポンス例

```json
{
  "object": "page",
  "id": "page-id",
  "last_edited_time": "2025-02-03T10:30:00.000Z",
  "properties": {
    "Status": {
      "id": "status",
      "type": "status",
      "status": {
        "name": "Completed",
        "color": "green"
      }
    }
  }
}
```

### 4. ページ取得（Retrieve a page）

#### エンドポイント

```
GET https://api.notion.com/v1/pages/{page_id}
```

#### レスポンス例

```json
{
  "object": "page",
  "id": "page-id",
  "created_time": "2025-01-15T10:00:00.000Z",
  "last_edited_time": "2025-02-03T10:30:00.000Z",
  "archived": false,
  "properties": {
    "Title": {
      "id": "title",
      "type": "title",
      "title": [
        {
          "type": "text",
          "text": {
            "content": "タスク名"
          }
        }
      ]
    }
  },
  "url": "https://www.notion.so/page-id"
}
```

---

## リクエスト/レスポンス形式

### 必須ヘッダー

すべての API リクエストには以下のヘッダーが必要です：

```http
Authorization: Bearer secret_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
Notion-Version: 2025-09-03
Content-Type: application/json
```

### フィルタ条件の書き方

#### 単一条件

```json
{
  "filter": {
    "property": "Status",
    "status": {
      "equals": "In Progress"
    }
  }
}
```

#### AND 条件（複数条件すべてを満たす）

```json
{
  "filter": {
    "and": [
      {
        "property": "Status",
        "status": {
          "equals": "In Progress"
        }
      },
      {
        "property": "Priority",
        "select": {
          "equals": "High"
        }
      }
    ]
  }
}
```

#### OR 条件（複数条件のいずれかを満たす）

```json
{
  "filter": {
    "or": [
      {
        "property": "Tags",
        "multi_select": {
          "contains": "urgent"
        }
      },
      {
        "property": "Tags",
        "multi_select": {
          "contains": "important"
        }
      }
    ]
  }
}
```

#### 複合条件（AND と OR の組み合わせ）

```json
{
  "filter": {
    "and": [
      {
        "property": "Done",
        "checkbox": {
          "equals": false
        }
      },
      {
        "or": [
          {
            "property": "Priority",
            "select": {
              "equals": "High"
            }
          },
          {
            "property": "Priority",
            "select": {
              "equals": "Medium"
            }
          }
        ]
      }
    ]
  }
}
```

### ソート条件の書き方

#### プロパティでソート

```json
{
  "sorts": [
    {
      "property": "Due Date",
      "direction": "ascending"
    }
  ]
}
```

#### タイムスタンプでソート

```json
{
  "sorts": [
    {
      "timestamp": "created_time",
      "direction": "descending"
    }
  ]
}
```

#### 複数のソート条件（優先順位順）

```json
{
  "sorts": [
    {
      "property": "Priority",
      "direction": "ascending"
    },
    {
      "property": "Due Date",
      "direction": "ascending"
    },
    {
      "timestamp": "created_time",
      "direction": "descending"
    }
  ]
}
```

### ページネーション

Notion API は結果をページ分割して返します。

#### 初回リクエスト

```json
{
  "page_size": 100
}
```

#### 次のページを取得

```json
{
  "start_cursor": "cursor-from-previous-response",
  "page_size": 100
}
```

#### レスポンスのページネーション情報

```json
{
  "results": [...],
  "next_cursor": "cursor-string-or-null",
  "has_more": true
}
```

- `has_more: true` の場合、次のページが存在
- `next_cursor` を使用して次のページをリクエスト
- すべてのページを取得するまで繰り返す

---

## プロパティ型とデータ構造

### Status プロパティ

#### スキーマ定義

```json
{
  "Status": {
    "id": "biOx",
    "name": "Status",
    "type": "status",
    "status": {
      "options": [
        {
          "id": "034ece9a-384d-4d1f-97f7-7f685b29ae9b",
          "name": "Not started",
          "color": "default"
        },
        {
          "id": "1234abcd-5678-90ef-ghij-klmnopqrstuv",
          "name": "In Progress",
          "color": "blue"
        },
        {
          "id": "wxyz5678-1234-abcd-efgh-ijklmnopqrst",
          "name": "Completed",
          "color": "green"
        }
      ],
      "groups": [
        {
          "id": "b9d42483-e576-4858-a26f-ed940a5f678f",
          "name": "To-do",
          "color": "gray",
          "option_ids": ["034ece9a-384d-4d1f-97f7-7f685b29ae9b"]
        },
        {
          "id": "f1234567-89ab-cdef-0123-456789abcdef",
          "name": "In progress",
          "color": "blue",
          "option_ids": ["1234abcd-5678-90ef-ghij-klmnopqrstuv"]
        },
        {
          "id": "g9876543-21ab-cdef-0123-456789abcdef",
          "name": "Complete",
          "color": "green",
          "option_ids": ["wxyz5678-1234-abcd-efgh-ijklmnopqrst"]
        }
      ]
    }
  }
}
```

#### 値の設定（ページ作成・更新時）

```json
{
  "Status": {
    "type": "status",
    "status": {
      "name": "In Progress"
    }
  }
}
```

#### 値の読み取り

```json
{
  "Status": {
    "id": "status",
    "type": "status",
    "status": {
      "name": "In Progress",
      "color": "blue"
    }
  }
}
```

#### 制約事項

- ⚠️ API 経由でステータスオプションの名前や値を更新することはできません
- オプションの追加・削除は Notion UI から行う必要があります

### Select プロパティ

#### スキーマ定義

```json
{
  "Priority": {
    "id": "%40Q%5BM",
    "name": "Priority",
    "type": "select",
    "select": {
      "options": [
        {
          "id": "e28f74fc-83a7-4469-8435-27eb18f9f9de",
          "name": "High",
          "color": "red"
        },
        {
          "id": "f3a5b6c7-d8e9-4f0a-b1c2-d3e4f5a6b7c8",
          "name": "Medium",
          "color": "yellow"
        },
        {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "name": "Low",
          "color": "gray"
        }
      ]
    }
  }
}
```

#### 値の設定

```json
{
  "Priority": {
    "type": "select",
    "select": {
      "name": "High"
    }
  }
}
```

または ID を使用：

```json
{
  "Priority": {
    "type": "select",
    "select": {
      "id": "e28f74fc-83a7-4469-8435-27eb18f9f9de"
    }
  }
}
```

#### 値のクリア

```json
{
  "Priority": {
    "type": "select",
    "select": null
  }
}
```

### Multi-select プロパティ

#### スキーマ定義

```json
{
  "Tags": {
    "id": "flsb",
    "name": "Tags",
    "type": "multi_select",
    "multi_select": {
      "options": [
        {
          "id": "5de29601-9c24-4b04-8629-0bca891c5120",
          "name": "urgent",
          "color": "red"
        },
        {
          "id": "7f8e9a0b-1c2d-3e4f-5a6b-7c8d9e0f1a2b",
          "name": "important",
          "color": "orange"
        },
        {
          "id": "3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
          "name": "personal",
          "color": "blue"
        }
      ]
    }
  }
}
```

#### 値の設定

```json
{
  "Tags": {
    "type": "multi_select",
    "multi_select": [
      {"name": "urgent"},
      {"name": "important"}
    ]
  }
}
```

#### 値のクリア

```json
{
  "Tags": {
    "type": "multi_select",
    "multi_select": []
  }
}
```

### Date プロパティ

#### スキーマ定義

```json
{
  "Due Date": {
    "id": "AJP%7D",
    "name": "Due Date",
    "type": "date",
    "date": {}
  }
}
```

#### 値の設定（日付のみ）

```json
{
  "Due Date": {
    "type": "date",
    "date": {
      "start": "2025-02-15",
      "end": null,
      "time_zone": null
    }
  }
}
```

#### 値の設定（日時）

```json
{
  "Due Date": {
    "type": "date",
    "date": {
      "start": "2025-02-15T14:30:00+09:00",
      "end": null,
      "time_zone": "Asia/Tokyo"
    }
  }
}
```

#### 値の設定（期間）

```json
{
  "Project Period": {
    "type": "date",
    "date": {
      "start": "2025-02-01",
      "end": "2025-02-28",
      "time_zone": null
    }
  }
}
```

#### 値のクリア

```json
{
  "Due Date": {
    "type": "date",
    "date": null
  }
}
```

### Title プロパティ

#### スキーマ定義

```json
{
  "Name": {
    "id": "title",
    "name": "Name",
    "type": "title",
    "title": {}
  }
}
```

#### 値の設定

```json
{
  "Name": {
    "type": "title",
    "title": [
      {
        "type": "text",
        "text": {
          "content": "タスクのタイトル"
        }
      }
    ]
  }
}
```

#### リッチテキストを含む設定

```json
{
  "Name": {
    "type": "title",
    "title": [
      {
        "type": "text",
        "text": {
          "content": "重要なタスク"
        },
        "annotations": {
          "bold": true,
          "italic": false,
          "strikethrough": false,
          "underline": false,
          "code": false,
          "color": "red"
        }
      }
    ]
  }
}
```

### Rich text プロパティ

#### スキーマ定義

```json
{
  "Description": {
    "id": "NZZ%3B",
    "name": "Description",
    "type": "rich_text",
    "rich_text": {}
  }
}
```

#### 値の設定

```json
{
  "Description": {
    "type": "rich_text",
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "タスクの詳細な説明をここに記載します。"
        }
      }
    ]
  }
}
```

#### 複数のテキスト要素

```json
{
  "Description": {
    "type": "rich_text",
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "これは "
        }
      },
      {
        "type": "text",
        "text": {
          "content": "重要な"
        },
        "annotations": {
          "bold": true
        }
      },
      {
        "type": "text",
        "text": {
          "content": " 説明です。"
        }
      }
    ]
  }
}
```

### Relation プロパティ

#### スキーマ定義

```json
{
  "Related Tasks": {
    "id": "~pex",
    "name": "Related Tasks",
    "type": "relation",
    "relation": {
      "data_source_id": "6c4240a9-a3ce-413e-9fd0-8a51a4d0a49b",
      "dual_property": {
        "synced_property_name": "Parent Task",
        "synced_property_id": "JU]K"
      }
    }
  }
}
```

#### 値の設定

```json
{
  "Related Tasks": {
    "type": "relation",
    "relation": [
      {"id": "page-id-1"},
      {"id": "page-id-2"}
    ]
  }
}
```

#### 制約事項

- リレーション先のデータベースもインテグレーションと共有されている必要があります
- リレーションのプロパティ値を取得するには、関連するデータベースへのアクセス権が必要です

---

## レート制限

### 制限値

Notion API のレート制限は以下の通りです：

- **平均**: 3 リクエスト/秒
- 短期的なバースト（一時的な高頻度リクエスト）は許容されますが、平均レートを超えないようにしてください

### 429 エラーの対処法

レート制限を超えると、API は HTTP ステータスコード `429` を返します。

#### エラーレスポンス例

```json
{
  "object": "error",
  "status": 429,
  "code": "rate_limited",
  "message": "Rate limit exceeded. Please retry after the time specified in the Retry-After header."
}
```

#### Retry-After ヘッダー

429 レスポンスには `Retry-After` ヘッダーが含まれます：

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 5
Content-Type: application/json
```

- `Retry-After` の値は秒数（整数）
- この秒数が経過してからリクエストを再試行してください

### 推奨されるリトライ戦略

#### 1. Retry-After ヘッダーベースのバックオフ

```python
import httpx
import time

def make_notion_request(client: httpx.Client, method: str, url: str, **kwargs):
    """Retry-After ヘッダーを尊重するリクエスト"""
    while True:
        response = client.request(method, url, **kwargs)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            continue
        
        return response
```

#### 2. キューベースのリクエスト管理

```python
import asyncio
from collections import deque

class NotionAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.request_queue = deque()
        self.rate_limit = 3  # requests per second
        
    async def enqueue_request(self, method: str, url: str, **kwargs):
        self.request_queue.append((method, url, kwargs))
    
    async def process_queue(self):
        """キューを消費してリクエストを送信"""
        while self.request_queue:
            if len(self.request_queue) > 0:
                method, url, kwargs = self.request_queue.popleft()
                # リクエストを送信
                await asyncio.sleep(1 / self.rate_limit)
```

#### 3. エクスポネンシャルバックオフ（補助的）

```python
import time
import random

def exponential_backoff(attempt: int, max_delay: int = 60):
    """エクスポネンシャルバックオフの待機時間を計算"""
    delay = min(2 ** attempt + random.uniform(0, 1), max_delay)
    return delay

def make_request_with_backoff(client: httpx.Client, method: str, url: str, max_retries: int = 5, **kwargs):
    """エクスポネンシャルバックオフでリトライ"""
    for attempt in range(max_retries):
        response = client.request(method, url, **kwargs)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 0))
            if retry_after > 0:
                time.sleep(retry_after)
            else:
                delay = exponential_backoff(attempt)
                time.sleep(delay)
            continue
        
        return response
    
    raise Exception(f"Max retries ({max_retries}) exceeded")
```

### 将来的な変更の可能性

- レート制限は今後変更される可能性があります
- ワークスペースの料金プランによって制限が異なる場合があります
- 最新の情報は[公式ドキュメント](https://developers.notion.com/reference/request-limits)を参照してください

---

## エラーハンドリング

### エラーレスポンスの形式

Notion API のエラーレスポンスは以下の形式です：

```json
{
  "object": "error",
  "status": 400,
  "code": "validation_error",
  "message": "body failed validation: body.properties.Status.status.name should be a string, instead was `undefined`."
}
```

### 主要なエラーコード

#### クライアントエラー（4xx）

##### 400 Bad Request

| コード | 説明 | 対処法 |
|--------|------|--------|
| `invalid_json` | リクエストボディが JSON としてデコードできない | JSON 形式を確認 |
| `invalid_request_url` | リクエスト URL が不正 | URL の形式を確認 |
| `invalid_request` | サポートされていない操作 | API ドキュメントで対応する操作を確認 |
| `validation_error` | パラメータが期待されるスキーマと一致しない | エラーメッセージの詳細を確認してパラメータを修正 |
| `missing_version` | `Notion-Version` ヘッダーが欠落 | リクエストヘッダーに `Notion-Version: 2025-09-03` を追加 |

##### 401 Unauthorized

| コード | 説明 | 対処法 |
|--------|------|--------|
| `unauthorized` | Bearer token が無効 | API キーが正しいか確認、環境変数の設定を確認 |

##### 403 Forbidden

| コード | 説明 | 対処法 |
|--------|------|--------|
| `restricted_resource` | 操作に必要な権限がない | インテグレーションの権限設定を確認、ページが共有されているか確認 |

##### 404 Not Found

| コード | 説明 | 対処法 |
|--------|------|--------|
| `object_not_found` | リソースが存在しないか、トークン所有者と共有されていない | リソース ID を確認、ページ/データベースがインテグレーションと共有されているか確認 |

#### サーバーエラー（5xx）

##### 409 Conflict

| コード | 説明 | 対処法 |
|--------|------|--------|
| `conflict_error` | トランザクションが失敗（データの衝突など） | 最新のデータを取得してからリトライ |

##### 429 Too Many Requests

| コード | 説明 | 対処法 |
|--------|------|--------|
| `rate_limited` | レート制限を超過 | `Retry-After` ヘッダーを確認して待機後にリトライ |

##### 500 Internal Server Error

| コード | 説明 | 対処法 |
|--------|------|--------|
| `internal_server_error` | 予期しないサーバーエラー | しばらく待ってからリトライ、問題が続く場合は Notion サポートに連絡 |

##### 503 Service Unavailable

| コード | 説明 | 対処法 |
|--------|------|--------|
| `service_unavailable` | Notion が一時的に利用不可、またはリクエストが 60 秒を超えた | しばらく待ってからリトライ |
| `database_connection_unavailable` | データベースにアクセスできない | しばらく待ってからリトライ |

##### 504 Gateway Timeout

| コード | 説明 | 対処法 |
|--------|------|--------|
| `gateway_timeout` | リクエストがタイムアウト | リクエストを簡素化するか、ページサイズを減らしてリトライ |

### エラーハンドリングの実装例

```python
import httpx
import time
from typing import Optional

class NotionAPIError(Exception):
    """Notion API のエラー基底クラス"""
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"[{status}] {code}: {message}")

class NotionClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2025-09-03",
            "Content-Type": "application/json"
        }
    
    def _handle_error_response(self, response: httpx.Response):
        """エラーレスポンスを処理"""
        try:
            error_data = response.json()
            status = error_data.get("status", response.status_code)
            code = error_data.get("code", "unknown_error")
            message = error_data.get("message", "An unknown error occurred")
            raise NotionAPIError(status, code, message)
        except ValueError:
            # JSON パースエラーの場合
            raise NotionAPIError(
                response.status_code,
                "parse_error",
                f"Failed to parse error response: {response.text}"
            )
    
    def make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
        max_retries: int = 3
    ) -> dict:
        """API リクエストを実行（エラーハンドリング付き）"""
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                with httpx.Client() as client:
                    response = client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=json_data,
                        timeout=60.0
                    )
                    
                    # レート制限のハンドリング
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        print(f"Rate limited. Retrying after {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue
                    
                    # コンフリクトエラーのハンドリング
                    if response.status_code == 409:
                        print(f"Conflict error. Retrying (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(2 ** attempt)  # エクスポネンシャルバックオフ
                        continue
                    
                    # サーバーエラーのハンドリング
                    if response.status_code >= 500:
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"Server error. Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self._handle_error_response(response)
                    
                    # クライアントエラー
                    if response.status_code >= 400:
                        self._handle_error_response(response)
                    
                    # 成功レスポンス
                    return response.json()
            
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Request error: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise
        
        raise Exception(f"Max retries ({max_retries}) exceeded")
```

---

## 実装例（Python + httpx）

### 基本的なクライアントクラス

```python
import httpx
from typing import Optional, List, Dict, Any

class NotionAPIClient:
    """Notion API クライアント"""
    
    def __init__(self, api_key: str):
        """
        Args:
            api_key: Notion Integration Token
        """
        self.api_key = api_key
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2025-09-03",
            "Content-Type": "application/json"
        }
    
    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None
    ) -> dict:
        """内部用リクエストメソッド"""
        url = f"{self.base_url}/{endpoint}"
        
        with httpx.Client() as client:
            response = client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_data,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
```

### データベースクエリの実装

```python
def query_database(
    self,
    database_id: str,
    filter_conditions: Optional[dict] = None,
    sorts: Optional[List[dict]] = None,
    page_size: int = 100
) -> List[dict]:
    """
    データベースをクエリしてページ一覧を取得
    
    Args:
        database_id: データベース ID
        filter_conditions: フィルタ条件
        sorts: ソート条件
        page_size: 1 ページあたりの結果数
    
    Returns:
        ページのリスト
    """
    endpoint = f"databases/{database_id}/query"
    
    # リクエストボディの構築
    request_body = {
        "page_size": page_size
    }
    
    if filter_conditions:
        request_body["filter"] = filter_conditions
    
    if sorts:
        request_body["sorts"] = sorts
    
    all_results = []
    has_more = True
    start_cursor = None
    
    # ページネーションで全件取得
    while has_more:
        if start_cursor:
            request_body["start_cursor"] = start_cursor
        
        response = self._request("POST", endpoint, request_body)
        
        all_results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
    
    return all_results

# 使用例
def get_in_progress_tasks(self, database_id: str) -> List[dict]:
    """進行中のタスクを取得"""
    return self.query_database(
        database_id=database_id,
        filter_conditions={
            "property": "Status",
            "status": {
                "equals": "In Progress"
            }
        },
        sorts=[
            {
                "property": "Due Date",
                "direction": "ascending"
            }
        ]
    )

def get_high_priority_tasks(self, database_id: str) -> List[dict]:
    """優先度が高いタスクを取得"""
    return self.query_database(
        database_id=database_id,
        filter_conditions={
            "and": [
                {
                    "property": "Status",
                    "status": {
                        "does_not_equal": "Completed"
                    }
                },
                {
                    "property": "Priority",
                    "select": {
                        "equals": "High"
                    }
                }
            ]
        }
    )
```

### ページ作成の実装

```python
def create_page(
    self,
    parent_database_id: str,
    properties: dict,
    children: Optional[List[dict]] = None
) -> dict:
    """
    新しいページを作成
    
    Args:
        parent_database_id: 親データベースの ID
        properties: ページプロパティ
        children: ページコンテンツ（ブロック）
    
    Returns:
        作成されたページ
    """
    endpoint = "pages"
    
    request_body = {
        "parent": {
            "type": "database_id",
            "database_id": parent_database_id
        },
        "properties": properties
    }
    
    if children:
        request_body["children"] = children
    
    return self._request("POST", endpoint, request_body)

# 使用例
def create_task(
    self,
    database_id: str,
    title: str,
    status: str = "Not started",
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> dict:
    """
    新しいタスクを作成
    
    Args:
        database_id: タスクデータベースの ID
        title: タスクのタイトル
        status: ステータス（デフォルト: "Not started"）
        priority: 優先度
        due_date: 期限（ISO 8601 形式: "2025-02-15"）
        tags: タグのリスト
    
    Returns:
        作成されたタスクページ
    """
    properties = {
        "Title": {
            "type": "title",
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }
            ]
        },
        "Status": {
            "type": "status",
            "status": {
                "name": status
            }
        }
    }
    
    # オプショナルなプロパティを追加
    if priority:
        properties["Priority"] = {
            "type": "select",
            "select": {
                "name": priority
            }
        }
    
    if due_date:
        properties["Due Date"] = {
            "type": "date",
            "date": {
                "start": due_date,
                "end": None,
                "time_zone": None
            }
        }
    
    if tags:
        properties["Tags"] = {
            "type": "multi_select",
            "multi_select": [
                {"name": tag} for tag in tags
            ]
        }
    
    return self.create_page(database_id, properties)
```

### ページ更新の実装

```python
def update_page(
    self,
    page_id: str,
    properties: dict
) -> dict:
    """
    ページのプロパティを更新
    
    Args:
        page_id: ページ ID
        properties: 更新するプロパティ
    
    Returns:
        更新されたページ
    """
    endpoint = f"pages/{page_id}"
    
    request_body = {
        "properties": properties
    }
    
    return self._request("PATCH", endpoint, request_body)

# 使用例
def update_task_status(
    self,
    page_id: str,
    status: str
) -> dict:
    """
    タスクのステータスを更新
    
    Args:
        page_id: タスクページの ID
        status: 新しいステータス
    
    Returns:
        更新されたタスクページ
    """
    return self.update_page(
        page_id=page_id,
        properties={
            "Status": {
                "type": "status",
                "status": {
                    "name": status
                }
            }
        }
    )

def complete_task(
    self,
    page_id: str,
    completed_date: Optional[str] = None
) -> dict:
    """
    タスクを完了としてマーク
    
    Args:
        page_id: タスクページの ID
        completed_date: 完了日（ISO 8601 形式）、省略時は今日の日付
    
    Returns:
        更新されたタスクページ
    """
    from datetime import date
    
    if not completed_date:
        completed_date = date.today().isoformat()
    
    return self.update_page(
        page_id=page_id,
        properties={
            "Status": {
                "type": "status",
                "status": {
                    "name": "Completed"
                }
            },
            "Completed Date": {
                "type": "date",
                "date": {
                    "start": completed_date,
                    "end": None,
                    "time_zone": None
                }
            }
        }
    )
```

### 完全な使用例

```python
import os
from datetime import date, timedelta

# API キーを環境変数から取得
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
DATABASE_ID = "your-database-id-here"

# クライアントの初期化
client = NotionAPIClient(NOTION_API_KEY)

# 1. 新しいタスクを作成
new_task = client.create_task(
    database_id=DATABASE_ID,
    title="Notion MCP サーバーの実装",
    status="In Progress",
    priority="High",
    due_date=(date.today() + timedelta(days=7)).isoformat(),
    tags=["development", "mcp", "notion"]
)
print(f"Created task: {new_task['id']}")

# 2. 進行中のタスクを取得
in_progress_tasks = client.get_in_progress_tasks(DATABASE_ID)
print(f"Found {len(in_progress_tasks)} tasks in progress")

for task in in_progress_tasks:
    title = task["properties"]["Title"]["title"][0]["text"]["content"]
    status = task["properties"]["Status"]["status"]["name"]
    print(f"  - {title} ({status})")

# 3. タスクのステータスを更新
if in_progress_tasks:
    first_task_id = in_progress_tasks[0]["id"]
    updated_task = client.update_task_status(
        page_id=first_task_id,
        status="Completed"
    )
    print(f"Updated task status: {updated_task['id']}")

# 4. タスクを完了としてマーク
completed_task = client.complete_task(
    page_id=new_task["id"],
    completed_date=date.today().isoformat()
)
print(f"Completed task: {completed_task['id']}")
```

---

## 参考資料

### 公式ドキュメント

- [Notion API Documentation](https://developers.notion.com/)
- [Authentication](https://developers.notion.com/docs/authorization)
- [Query a database](https://developers.notion.com/reference/post-database-query)
- [Create a page](https://developers.notion.com/reference/post-page)
- [Update page properties](https://developers.notion.com/reference/patch-page)
- [Data source properties](https://developers.notion.com/reference/property-object)
- [Request limits](https://developers.notion.com/reference/request-limits)
- [Error codes](https://developers.notion.com/reference/errors)

### コミュニティリソース

- [notion-sdk-py](https://github.com/ramnes/notion-sdk-py) - Python SDK（公式ではないが広く使われている）
- [Notion API Examples](https://developers.notion.com/docs/examples) - 公式サンプルコード集

---

## 変更履歴

- **2026-02-03**: 初版作成
  - API バージョン 2025-09-03 に基づく情報を記載
  - 認証、エンドポイント、プロパティ型、レート制限、エラーハンドリングを網羅
  - Python + httpx による実装例を追加
