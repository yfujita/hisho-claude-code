# Google Calendar API リファレンス

最終更新日: 2026年2月4日

## 目次

1. [概要](#概要)
2. [認証方法](#認証方法)
3. [主要なエンドポイント](#主要なエンドポイント)
4. [データモデル](#データモデル)
5. [レート制限とクォータ](#レート制限とクォータ)
6. [料金体系](#料金体系)
7. [SDK/ライブラリ](#sdkライブラリ)
8. [ベストプラクティス](#ベストプラクティス)
9. [コード例（Python）](#コード例python)

---

## 概要

Google Calendar APIは、プログラムから Google Calendar にアクセスし、カレンダーとイベントの読み取り・更新を可能にするAPIです。Java、JavaScript、Pythonなど、複数のプログラミング言語で利用できます。

### 主な機能

- **イベント管理**: カレンダーイベントの作成、読み取り、更新、削除
- **カレンダー操作**: カレンダーの作成、設定変更、共有管理
- **アクセス制御**: ユーザーやグループごとのアクセス権限設定
- **フリー/ビジー情報**: ユーザーのスケジュール状況の取得
- **プッシュ通知**: カレンダー変更の通知受信

### 主要なリソース

1. **Events（イベント）**: タイトル、開始/終了時刻、参加者などを含むカレンダーイベント（単発イベントまたは定期イベント）
2. **Calendars（カレンダー）**: 各ユーザーはプライマリカレンダーと、その他のアクセス可能なカレンダーを持つ
3. **Access Control Rules（ACL）**: ユーザーやグループに対するカレンダーへのアクセス権限
4. **その他のリソース**: CalendarList、Channels、Colors、Freebusy、Settings

### 最近の機能追加（2025年末時点）

- `events.watch()` メソッドで `eventTypes` フィールドをクエリパラメータとしてサポート
- Working Locations（勤務場所）の読み取りと更新が一般提供開始
- Google Contactsから自動作成される誕生日イベントへのアクセスが可能に

---

## 認証方法

Google Calendar APIでは、OAuth 2.0による認証を使用します。

### OAuth 2.0

#### 1. ユーザー認証（Web Server Applications）

エンドユーザーの代わりにAPIにアクセスする場合に使用します。

**フロー:**
1. Google Cloud Consoleでクライアント認証情報を作成
2. ユーザーを認可エンドポイントにリダイレクト
3. ユーザーが権限を承認
4. 認可コードを取得
5. 認可コードをアクセストークンに交換
6. アクセストークンを使用してAPIを呼び出し

**必要なスコープ:**
- `https://www.googleapis.com/auth/calendar` - カレンダーへの完全アクセス
- `https://www.googleapis.com/auth/calendar.readonly` - 読み取り専用アクセス
- `https://www.googleapis.com/auth/calendar.events` - イベントへのアクセス

#### 2. サービスアカウント（Service Account）

サーバー間通信で使用するアカウント。エンドユーザーではなく、アプリケーションに属します。

**特徴:**
- 個別のユーザー関与なし、アプリケーションがサービスアカウントとして動作
- JSON Web Token（JWT）を使用した暗号化署名
- Google Workspaceドメイン管理者は、サービスアカウントにドメイン全体の権限委譲が可能

**セットアップ手順:**
1. Google Cloud ConsoleでAPIを有効化
2. サービスアカウントを作成
3. 認証情報（JSONキーファイル）をダウンロード
4. アクセストークンをリクエスト
5. アクセストークンを使用してAPIを呼び出し

**セキュリティ上の注意:**
- サービスアカウントの認証は暗号化処理が複雑なため、Google公式クライアントライブラリの使用を強く推奨
- JWTの作成と署名を手動で行うとセキュリティリスクが高まる

---

## 主要なエンドポイント

### ベースURL

```
https://www.googleapis.com/calendar/v3
```

### 1. カレンダー操作（Calendars）

#### カレンダー一覧取得
```
GET /users/me/calendarList
```

#### カレンダー作成
```
POST /calendars
```

#### カレンダー取得
```
GET /calendars/{calendarId}
```

#### カレンダー更新
```
PUT /calendars/{calendarId}
```

#### カレンダー削除
```
DELETE /calendars/{calendarId}
```

### 2. イベント操作（Events）

#### イベント一覧取得
```
GET /calendars/{calendarId}/events
```

**主なクエリパラメータ:**
- `timeMin` / `timeMax`: 期間指定
- `q`: キーワード検索
- `orderBy`: 並び順（startTime, updated）
- `singleEvents`: 定期イベントを展開するか
- `eventTypes`: イベントタイプでフィルタリング

#### イベント取得
```
GET /calendars/{calendarId}/events/{eventId}
```

#### イベント作成
```
POST /calendars/{calendarId}/events
```

#### イベント更新
```
PUT /calendars/{calendarId}/events/{eventId}
PATCH /calendars/{calendarId}/events/{eventId}  # 部分更新
```

#### イベント削除
```
DELETE /calendars/{calendarId}/events/{eventId}
```

#### イベント移動
```
POST /calendars/{calendarId}/events/{eventId}/move
```

別のカレンダーにイベントを移動（主催者を変更）

#### イベントインスタンス取得
```
GET /calendars/{calendarId}/events/{eventId}/instances
```

定期イベントの個別インスタンスを取得

#### イベントインポート
```
POST /calendars/{calendarId}/events/import
```

既存イベントのプライベートコピーを追加

### 3. アクセス制御リスト（ACL）

#### ACL一覧取得
```
GET /calendars/{calendarId}/acl
```

#### ACL作成
```
POST /calendars/{calendarId}/acl
```

#### ACL更新
```
PUT /calendars/{calendarId}/acl/{ruleId}
```

#### ACL削除
```
DELETE /calendars/{calendarId}/acl/{ruleId}
```

### 4. フリー/ビジー情報（Freebusy）

```
POST /freeBusy
```

複数のカレンダーのフリー/ビジー情報を取得

### 5. その他のリソース

- **Colors**: カレンダーとイベントの色定義を取得
- **Settings**: ユーザーの設定を取得
- **Channels**: プッシュ通知の設定

---

## データモデル

### Event（イベント）リソース

```json
{
  "id": "string",
  "status": "confirmed | tentative | cancelled",
  "summary": "イベントのタイトル",
  "description": "イベントの説明",
  "location": "イベントの場所",
  "colorId": "string",
  "creator": {
    "email": "string",
    "displayName": "string"
  },
  "organizer": {
    "email": "string",
    "displayName": "string"
  },
  "start": {
    "dateTime": "2026-02-04T10:00:00+09:00",
    "timeZone": "Asia/Tokyo"
  },
  "end": {
    "dateTime": "2026-02-04T11:00:00+09:00",
    "timeZone": "Asia/Tokyo"
  },
  "recurrence": [
    "RRULE:FREQ=DAILY;COUNT=10"
  ],
  "attendees": [
    {
      "email": "string",
      "displayName": "string",
      "responseStatus": "needsAction | declined | tentative | accepted"
    }
  ],
  "reminders": {
    "useDefault": false,
    "overrides": [
      {
        "method": "email | popup",
        "minutes": 30
      }
    ]
  },
  "visibility": "default | public | private | confidential",
  "created": "2026-02-04T09:00:00.000Z",
  "updated": "2026-02-04T09:00:00.000Z"
}
```

#### 主要フィールド

| フィールド | 型 | 説明 |
|----------|-----|------|
| `id` | string | イベント識別子 |
| `summary` | string | イベントのタイトル |
| `description` | string | イベントの説明 |
| `start` | object | 開始時刻（dateTimeとtimeZone） |
| `end` | object | 終了時刻（dateTimeとtimeZone） |
| `attendees` | array | 参加者リスト |
| `recurrence` | array | 定期イベントのルール（RRULE、EXRULE、RDATE、EXDATE） |
| `reminders` | object | リマインダー設定 |
| `status` | string | イベントステータス（confirmed、tentative、cancelled） |
| `visibility` | string | 公開範囲 |

### Calendar（カレンダー）リソース

```json
{
  "id": "string",
  "summary": "カレンダーのタイトル",
  "description": "カレンダーの説明",
  "location": "地理的な場所",
  "timeZone": "Asia/Tokyo",
  "conferenceProperties": {
    "allowedConferenceSolutionTypes": ["hangoutsMeet"]
  }
}
```

#### 主要フィールド

| フィールド | 型 | 説明 |
|----------|-----|------|
| `id` | string | カレンダー識別子 |
| `summary` | string | カレンダーのタイトル |
| `description` | string | カレンダーの説明 |
| `timeZone` | string | 地理的タイムゾーン |
| `location` | string | 地理的な場所 |

### CalendarListEntry（カレンダーリスト）リソース

ユーザーのカレンダーリストに表示されるカレンダーの情報。

```json
{
  "id": "string",
  "summary": "string",
  "description": "string",
  "timeZone": "string",
  "colorId": "string",
  "backgroundColor": "#9fc6e7",
  "foregroundColor": "#000000",
  "selected": true,
  "accessRole": "freeBusyReader | reader | writer | owner",
  "defaultReminders": [
    {
      "method": "email",
      "minutes": 30
    }
  ],
  "primary": false
}
```

### ACL（アクセス制御リスト）リソース

```json
{
  "id": "string",
  "scope": {
    "type": "default | user | group | domain",
    "value": "user@example.com"
  },
  "role": "freeBusyReader | reader | writer | owner"
}
```

---

## レート制限とクォータ

### 基本情報

- **料金**: すべてのGoogle Calendar APIの使用は無料
- **クォータ超過**: クォータを超えても追加料金は発生せず、アカウントへの請求もなし

### クォータ制限（2021年5月以降）

APIクエリは分単位で監視・制限されます。

#### デフォルトクォータ

- **1日あたりのリクエスト数**: 1,000,000リクエスト/プロジェクト/日（ほとんどのユーザー）
- **1分あたりのリクエスト数（プロジェクト単位）**: プロジェクトごとの分単位制限
- **1分あたりのリクエスト数（ユーザー単位）**: プロジェクト内の特定ユーザーごとの分単位制限

### エラーレスポンス

クォータを超過した場合:
- **403 usageLimits**: レート制限超過
- **429 usageLimits**: レート制限超過

クォータを超過すると、リクエストは失敗せず、クォータが利用可能になるまでレート制限されます。

### クォータ増加のリクエスト

クォータの増加は可能ですが、以下の理由から推奨されません:
- アプリケーションが他のタイプの制限（一般的なカレンダー使用制限、運用制限）に達する可能性がある

**リクエスト方法:**
1. Google API Consoleの「Enabled APIs」ページにアクセス
2. 「Quotas」セクションに移動
3. 増加リクエストを送信

---

## 料金体系

### 無料枠

**Google Calendar APIはすべて無料で利用できます。**

- クォータ制限内であれば、追加料金は一切発生しません
- クォータを超過しても課金されることはありません
- エンタープライズサポートが必要な場合を除き、基本的に無料で使用可能

---

## SDK/ライブラリ

### 公式クライアントライブラリ

Google は複数のプログラミング言語向けに公式クライアントライブラリを提供しています。

#### Python

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

**主要なモジュール:**
- `google-api-python-client`: Google API Pythonクライアント
- `google-auth-httplib2`: 認証用HTTPライブラリ
- `google-auth-oauthlib`: OAuth 2.0認証

#### Node.js

```bash
npm install googleapis
```

#### Java

```xml
<dependency>
  <groupId>com.google.apis</groupId>
  <artifactId>google-api-services-calendar</artifactId>
  <version>v3-rev20230825-2.0.0</version>
</dependency>
```

#### その他の言語

- **Go**: `google.golang.org/api/calendar/v3`
- **PHP**: `google/apiclient`
- **.NET**: `Google.Apis.Calendar.v3`
- **Ruby**: `google-api-client`

### 推奨事項

- **公式ライブラリの使用を強く推奨**: 認証処理、エラーハンドリング、リトライロジックが組み込まれている
- **セキュリティ**: JWTの作成や暗号化処理を手動で行うとセキュリティリスクが高まるため、ライブラリの使用が必須

---

## ベストプラクティス

### 1. パフォーマンス最適化

#### gzip圧縮の有効化

帯域幅を削減し、パフォーマンスを向上させます。

```python
# Pythonの例
service = build('calendar', 'v3', credentials=credentials)
# デフォルトでgzip圧縮が有効
```

#### 部分レスポンスの使用

必要なフィールドのみをリクエストし、データ転送量を削減します。

```python
# 必要なフィールドのみを取得
events = service.events().list(
    calendarId='primary',
    fields='items(id,summary,start,end)'
).execute()
```

#### PATCH リクエストの使用

リソースを変更する際は、完全な表現ではなく、変更したいフィールドのみを送信します。

```python
# 部分更新
event = {
    'summary': '新しいタイトル'
}
updated_event = service.events().patch(
    calendarId='primary',
    eventId='eventId',
    body=event
).execute()
```

### 2. クォータ管理とレート制限

#### トラフィックの分散

- **1日を通じてトラフィックを分散**: 可能な限り、APIコールを1日全体に分散させる
- **ランダム化**: 定期的な同期を行う場合、各クライアントで異なるランダムな時間を設定
- **間隔の変動**: 定期処理の間隔を±25%変動させて、トラフィックをより均等に分散

```python
import random
import time

# ランダムな遅延を追加
delay = random.uniform(0.75, 1.25) * base_interval
time.sleep(delay)
```

#### エラーハンドリングと指数バックオフ

レート制限エラーが発生した場合、指数バックオフを実装します。

```python
import time
from googleapiclient.errors import HttpError

def call_api_with_backoff(service, max_retries=5):
    for n in range(max_retries):
        try:
            return service.events().list(calendarId='primary').execute()
        except HttpError as error:
            if error.resp.status in [403, 429]:
                # 指数バックオフ
                wait_time = (2 ** n) + random.uniform(0, 1)
                print(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")
```

#### バッチ処理

複数のAPIリクエストをバッチ化して、リクエスト数を削減します。

```python
from googleapiclient.http import BatchHttpRequest

def batch_callback(request_id, response, exception):
    if exception:
        print(f"Error: {exception}")
    else:
        print(f"Success: {response}")

batch = service.new_batch_http_request(callback=batch_callback)
batch.add(service.events().get(calendarId='primary', eventId='event1'))
batch.add(service.events().get(calendarId='primary', eventId='event2'))
batch.execute()
```

#### quotaUser パラメータの使用

サービスアカウントを使用する場合、`quotaUser`パラメータでクォータを計算するユーザーを指定します。

```python
events = service.events().list(
    calendarId='primary',
    quotaUser='user@example.com'
).execute()
```

### 3. プッシュ通知の使用

ポーリングの代わりにプッシュ通知を使用して、リソースの変更を監視します。

```python
# Webhook URLを設定
channel = {
    'id': 'unique-channel-id',
    'type': 'web_hook',
    'address': 'https://your-domain.com/notifications'
}

# プッシュ通知を開始
watch_response = service.events().watch(
    calendarId='primary',
    body=channel
).execute()
```

### 4. キャッシュの活用

よくあるクエリ（例: 「今後7日間」）の結果をキャッシュします。

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=128)
def get_upcoming_events(days=7):
    now = datetime.utcnow().isoformat() + 'Z'
    end = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])
```

### 5. セキュリティのベストプラクティス

- **最小権限の原則**: 必要最小限のスコープのみをリクエスト
- **認証情報の保護**: APIキーやOAuth認証情報を安全に保管（環境変数、シークレット管理サービス）
- **HTTPS の使用**: すべてのAPI通信でHTTPSを使用
- **トークンの有効期限管理**: アクセストークンの有効期限を適切に管理し、必要に応じて更新

---

## コード例（Python）

### 1. セットアップと認証

#### OAuth 2.0（ユーザー認証）

```python
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import pickle

# 必要なスコープを定義
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Google Calendar APIサービスを取得"""
    creds = None
    
    # token.pickleファイルにユーザーのアクセストークンとリフレッシュトークンを保存
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 有効な認証情報がない場合、ユーザーにログインを求める
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 次回実行時のために認証情報を保存
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    service = build('calendar', 'v3', credentials=creds)
    return service
```

#### サービスアカウント認証

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service-account-key.json'

def get_calendar_service_with_service_account():
    """サービスアカウントでGoogle Calendar APIサービスを取得"""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    
    service = build('calendar', 'v3', credentials=credentials)
    return service

def get_calendar_service_with_delegation(user_email):
    """ドメイン全体の権限委譲を使用してサービスを取得"""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    
    # 特定のユーザーに代わって動作
    delegated_credentials = credentials.with_subject(user_email)
    
    service = build('calendar', 'v3', credentials=delegated_credentials)
    return service
```

### 2. カレンダー操作

#### カレンダー一覧を取得

```python
def list_calendars(service):
    """ユーザーのカレンダー一覧を取得"""
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        if not calendars:
            print('カレンダーが見つかりませんでした。')
            return []
        
        print('カレンダー一覧:')
        for calendar in calendars:
            print(f"- {calendar['summary']} (ID: {calendar['id']})")
        
        return calendars
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return []
```

#### カレンダーを作成

```python
def create_calendar(service, summary, description=None, timezone='Asia/Tokyo'):
    """新しいカレンダーを作成"""
    calendar = {
        'summary': summary,
        'timeZone': timezone
    }
    
    if description:
        calendar['description'] = description
    
    try:
        created_calendar = service.calendars().insert(body=calendar).execute()
        print(f"カレンダーを作成しました: {created_calendar['summary']}")
        print(f"カレンダーID: {created_calendar['id']}")
        return created_calendar
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None
```

### 3. イベント操作

#### イベント一覧を取得

```python
from datetime import datetime, timedelta

def list_upcoming_events(service, calendar_id='primary', max_results=10):
    """今後のイベント一覧を取得"""
    try:
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z'はUTC時間を示す
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            print('今後のイベントはありません。')
            return []
        
        print(f'今後の{len(events)}件のイベント:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"- {start}: {event['summary']}")
        
        return events
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return []
```

#### 期間を指定してイベントを取得

```python
def get_events_in_range(service, start_date, end_date, calendar_id='primary'):
    """指定期間のイベントを取得"""
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_date.isoformat() + 'Z',
            timeMax=end_date.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        print(f'{len(events)}件のイベントが見つかりました。')
        return events
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return []
```

#### イベントを作成

```python
def create_event(service, summary, start_time, end_time, 
                 description=None, location=None, attendees=None,
                 calendar_id='primary', timezone='Asia/Tokyo'):
    """新しいイベントを作成"""
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': timezone,
        },
    }
    
    if description:
        event['description'] = description
    
    if location:
        event['location'] = location
    
    if attendees:
        event['attendees'] = [{'email': email} for email in attendees]
    
    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()
        
        print(f"イベントを作成しました: {created_event['summary']}")
        print(f"イベントURL: {created_event.get('htmlLink')}")
        return created_event
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None


# 使用例
if __name__ == '__main__':
    service = get_calendar_service()
    
    # 1時間後に開始、2時間のイベントを作成
    start = datetime.now() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    
    create_event(
        service,
        summary='ミーティング',
        start_time=start,
        end_time=end,
        description='重要なミーティング',
        location='会議室A',
        attendees=['user1@example.com', 'user2@example.com']
    )
```

#### 終日イベントを作成

```python
def create_all_day_event(service, summary, date, calendar_id='primary'):
    """終日イベントを作成"""
    event = {
        'summary': summary,
        'start': {
            'date': date.strftime('%Y-%m-%d'),
        },
        'end': {
            'date': (date + timedelta(days=1)).strftime('%Y-%m-%d'),
        },
    }
    
    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()
        
        print(f"終日イベントを作成しました: {created_event['summary']}")
        return created_event
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None
```

#### 定期イベントを作成

```python
def create_recurring_event(service, summary, start_time, end_time,
                          recurrence_rule, calendar_id='primary',
                          timezone='Asia/Tokyo'):
    """定期イベントを作成"""
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': timezone,
        },
        'recurrence': [
            recurrence_rule
        ],
    }
    
    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()
        
        print(f"定期イベントを作成しました: {created_event['summary']}")
        return created_event
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None


# 使用例: 毎週月曜日10:00-11:00に10回繰り返す
if __name__ == '__main__':
    service = get_calendar_service()
    
    start = datetime(2026, 2, 9, 10, 0, 0)  # 2026年2月9日（月曜日）10:00
    end = datetime(2026, 2, 9, 11, 0, 0)    # 2026年2月9日 11:00
    
    create_recurring_event(
        service,
        summary='週次ミーティング',
        start_time=start,
        end_time=end,
        recurrence_rule='RRULE:FREQ=WEEKLY;COUNT=10'
    )
```

#### イベントを更新

```python
def update_event(service, event_id, calendar_id='primary', **updates):
    """既存のイベントを更新"""
    try:
        # 既存のイベントを取得
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # 更新内容を適用
        for key, value in updates.items():
            event[key] = value
        
        # イベントを更新
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        print(f"イベントを更新しました: {updated_event['summary']}")
        return updated_event
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None


# 使用例: タイトルと場所を更新
update_event(
    service,
    event_id='event123',
    summary='新しいタイトル',
    location='新しい場所'
)
```

#### イベントを部分更新（PATCH）

```python
def patch_event(service, event_id, calendar_id='primary', **updates):
    """イベントを部分更新（変更箇所のみ送信）"""
    try:
        updated_event = service.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body=updates
        ).execute()
        
        print(f"イベントを更新しました: {updated_event['summary']}")
        return updated_event
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None


# 使用例: タイトルのみを更新
patch_event(service, event_id='event123', summary='新しいタイトル')
```

#### イベントを削除

```python
def delete_event(service, event_id, calendar_id='primary'):
    """イベントを削除"""
    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        print(f"イベントを削除しました: {event_id}")
        return True
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return False
```

#### イベントを検索

```python
def search_events(service, query, calendar_id='primary', max_results=10):
    """キーワードでイベントを検索"""
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            q=query,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            print(f'「{query}」に一致するイベントは見つかりませんでした。')
            return []
        
        print(f'「{query}」に一致する{len(events)}件のイベント:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"- {start}: {event['summary']}")
        
        return events
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return []
```

### 4. フリー/ビジー情報の取得

```python
def get_freebusy(service, calendar_ids, time_min, time_max):
    """複数のカレンダーのフリー/ビジー情報を取得"""
    body = {
        "timeMin": time_min.isoformat() + 'Z',
        "timeMax": time_max.isoformat() + 'Z',
        "items": [{"id": cal_id} for cal_id in calendar_ids]
    }
    
    try:
        freebusy_result = service.freebusy().query(body=body).execute()
        calendars = freebusy_result.get('calendars', {})
        
        for cal_id, cal_data in calendars.items():
            print(f"\nカレンダー: {cal_id}")
            busy_periods = cal_data.get('busy', [])
            
            if not busy_periods:
                print("  ビジーな時間はありません")
            else:
                print(f"  {len(busy_periods)}件のビジーな時間:")
                for period in busy_periods:
                    print(f"  - {period['start']} 〜 {period['end']}")
        
        return freebusy_result
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None


# 使用例: 今日のフリー/ビジー情報を取得
if __name__ == '__main__':
    service = get_calendar_service()
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    get_freebusy(
        service,
        calendar_ids=['primary', 'user@example.com'],
        time_min=today_start,
        time_max=today_end
    )
```

### 5. ACL（アクセス制御リスト）操作

#### ACL一覧を取得

```python
def list_acl(service, calendar_id='primary'):
    """カレンダーのACL一覧を取得"""
    try:
        acl_list = service.acl().list(calendarId=calendar_id).execute()
        rules = acl_list.get('items', [])
        
        if not rules:
            print('ACLルールが見つかりませんでした。')
            return []
        
        print('ACLルール一覧:')
        for rule in rules:
            scope = rule['scope']
            print(f"- {scope['type']}: {scope.get('value', 'N/A')} (role: {rule['role']})")
        
        return rules
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return []
```

#### ACLルールを追加

```python
def add_acl_rule(service, user_email, role='reader', calendar_id='primary'):
    """カレンダーにACLルールを追加
    
    Args:
        role: 'freeBusyReader', 'reader', 'writer', 'owner'
    """
    rule = {
        'scope': {
            'type': 'user',
            'value': user_email,
        },
        'role': role
    }
    
    try:
        created_rule = service.acl().insert(
            calendarId=calendar_id,
            body=rule
        ).execute()
        
        print(f"ACLルールを追加しました: {user_email} ({role})")
        return created_rule
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None
```

#### ACLルールを削除

```python
def delete_acl_rule(service, rule_id, calendar_id='primary'):
    """ACLルールを削除"""
    try:
        service.acl().delete(
            calendarId=calendar_id,
            ruleId=rule_id
        ).execute()
        
        print(f"ACLルールを削除しました: {rule_id}")
        return True
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return False
```

### 6. プッシュ通知の設定

```python
import uuid

def setup_push_notification(service, webhook_url, calendar_id='primary'):
    """カレンダーイベントの変更通知を受け取るWebhookを設定"""
    channel = {
        'id': str(uuid.uuid4()),
        'type': 'web_hook',
        'address': webhook_url,
        'expiration': int((datetime.now() + timedelta(days=7)).timestamp() * 1000)
    }
    
    try:
        watch_response = service.events().watch(
            calendarId=calendar_id,
            body=channel
        ).execute()
        
        print(f"プッシュ通知を設定しました")
        print(f"Channel ID: {watch_response['id']}")
        print(f"Resource ID: {watch_response['resourceId']}")
        print(f"Expiration: {watch_response['expiration']}")
        
        return watch_response
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return None


def stop_push_notification(service, channel_id, resource_id):
    """プッシュ通知を停止"""
    channel = {
        'id': channel_id,
        'resourceId': resource_id
    }
    
    try:
        service.channels().stop(body=channel).execute()
        print(f"プッシュ通知を停止しました")
        return True
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return False
```

### 7. バッチ処理

```python
def batch_get_events(service, event_ids, calendar_id='primary'):
    """複数のイベントを一度に取得"""
    def callback(request_id, response, exception):
        if exception:
            print(f"Request {request_id} failed: {exception}")
        else:
            print(f"Event: {response['summary']}")
    
    try:
        batch = service.new_batch_http_request(callback=callback)
        
        for event_id in event_ids:
            batch.add(service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ))
        
        batch.execute()
        return True
    except Exception as e:
        print(f'エラーが発生しました: {e}')
        return False
```

### 8. エラーハンドリングの例

```python
from googleapiclient.errors import HttpError
import time
import random

def robust_api_call(api_call_func, max_retries=5):
    """エラーハンドリングとリトライを含むAPI呼び出し"""
    for attempt in range(max_retries):
        try:
            return api_call_func()
        except HttpError as error:
            error_code = error.resp.status
            
            # レート制限エラー
            if error_code in [403, 429]:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"レート制限エラー。{wait_time:.2f}秒待機します...")
                time.sleep(wait_time)
            
            # 認証エラー
            elif error_code == 401:
                print("認証エラー。認証情報を確認してください。")
                raise
            
            # リソース未検出
            elif error_code == 404:
                print("リソースが見つかりません。")
                raise
            
            # その他のエラー
            else:
                print(f"APIエラー: {error}")
                raise
        
        except Exception as e:
            print(f"予期しないエラー: {e}")
            raise
    
    raise Exception(f"{max_retries}回のリトライ後も失敗しました")


# 使用例
def get_events_safely(service):
    def api_call():
        return service.events().list(calendarId='primary').execute()
    
    return robust_api_call(api_call)
```

### 9. 完全な実装例

```python
#!/usr/bin/env python3
"""
Google Calendar API使用例
"""

from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os.path
import pickle

SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    """メイン処理"""
    # 認証
    service = get_calendar_service()
    
    # カレンダー一覧を表示
    print("=== カレンダー一覧 ===")
    list_calendars(service)
    
    # 今後10件のイベントを表示
    print("\n=== 今後のイベント ===")
    list_upcoming_events(service, max_results=10)
    
    # 新しいイベントを作成
    print("\n=== イベント作成 ===")
    start = datetime.now() + timedelta(days=1)
    end = start + timedelta(hours=1)
    
    event = create_event(
        service,
        summary='テストイベント',
        start_time=start,
        end_time=end,
        description='Google Calendar APIのテスト',
        location='オンライン'
    )
    
    if event:
        # 作成したイベントを更新
        print("\n=== イベント更新 ===")
        patch_event(
            service,
            event_id=event['id'],
            summary='更新されたテストイベント'
        )
        
        # 作成したイベントを削除
        print("\n=== イベント削除 ===")
        delete_event(service, event_id=event['id'])


def get_calendar_service():
    """Google Calendar APIサービスを取得"""
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)


def list_calendars(service):
    """カレンダー一覧を取得"""
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        for calendar in calendars:
            print(f"- {calendar['summary']} (ID: {calendar['id']})")
        
        return calendars
    except HttpError as error:
        print(f'エラー: {error}')
        return []


def list_upcoming_events(service, calendar_id='primary', max_results=10):
    """今後のイベント一覧を取得"""
    try:
        now = datetime.utcnow().isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"- {start}: {event['summary']}")
        
        return events
    except HttpError as error:
        print(f'エラー: {error}')
        return []


def create_event(service, summary, start_time, end_time, 
                 description=None, location=None, calendar_id='primary',
                 timezone='Asia/Tokyo'):
    """イベントを作成"""
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': timezone,
        },
    }
    
    if description:
        event['description'] = description
    
    if location:
        event['location'] = location
    
    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()
        
        print(f"イベントを作成しました: {created_event['summary']}")
        print(f"URL: {created_event.get('htmlLink')}")
        
        return created_event
    except HttpError as error:
        print(f'エラー: {error}')
        return None


def patch_event(service, event_id, calendar_id='primary', **updates):
    """イベントを部分更新"""
    try:
        updated_event = service.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body=updates
        ).execute()
        
        print(f"イベントを更新しました: {updated_event['summary']}")
        return updated_event
    except HttpError as error:
        print(f'エラー: {error}')
        return None


def delete_event(service, event_id, calendar_id='primary'):
    """イベントを削除"""
    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        print(f"イベントを削除しました: {event_id}")
        return True
    except HttpError as error:
        print(f'エラー: {error}')
        return False


if __name__ == '__main__':
    main()
```

---

## 参考リンク

- [Google Calendar API 公式ドキュメント](https://developers.google.com/workspace/calendar)
- [API リファレンス](https://developers.google.com/workspace/calendar/api/v3/reference)
- [Python クイックスタート](https://developers.google.com/calendar/api/quickstart/python)
- [OAuth 2.0 ガイド](https://developers.google.com/identity/protocols/oauth2)
- [クォータ管理](https://developers.google.com/workspace/calendar/api/guides/quota)
- [パフォーマンスのヒント](https://developers.google.com/workspace/calendar/api/guides/performance)

---

## ソース

- [Google Calendar API overview | Google for Developers](https://developers.google.com/workspace/calendar/api/guides/overview)
- [API Reference | Google Calendar | Google for Developers](https://developers.google.com/workspace/calendar/api/v3/reference)
- [Using OAuth 2.0 for Server to Server Applications | Google for Developers](https://developers.google.com/identity/protocols/oauth2/service-account)
- [Using OAuth 2.0 to Access Google APIs | Google for Developers](https://developers.google.com/identity/protocols/oauth2)
- [Events | Google Calendar | Google for Developers](https://developers.google.com/workspace/calendar/api/v3/reference/events)
- [Manage quotas | Google Calendar | Google for Developers](https://developers.google.com/workspace/calendar/api/guides/quota)
- [Performance tips | Google Calendar | Google for Developers](https://developers.google.com/workspace/calendar/api/guides/performance)
