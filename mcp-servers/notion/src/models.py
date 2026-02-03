"""Pydantic models for Notion API integration.

このモジュールは、Notion APIのレスポンスとリクエストを型安全に扱うための
Pydanticモデルを定義しています。
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """タスクのステータス.

    Notionデータベースで使用されるステータスの値。
    実際のNotion設定に合わせて日本語値を使用。
    """

    NOT_STARTED = "未着手"
    TODAY = "今日やる"
    IN_PROGRESS = "対応中"
    BACKLOG = "バックログ"
    COMPLETED = "完了 🙌"
    CANCELLED = "キャンセル"


class TaskPriority(str, Enum):
    """タスクの優先度.

    Notionデータベースで使用される優先度の値。
    """

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Task(BaseModel):
    """タスクモデル.

    Notionのタスクデータベースのページを表現するモデル。
    Notion APIのレスポンスから必要な情報を抽出して保持します。
    """

    id: str = Field(..., description="ページID（Notion内部ID）")
    title: str = Field(..., description="タスクのタイトル")
    status: TaskStatus = Field(..., description="タスクのステータス")
    priority: Optional[TaskPriority] = Field(None, description="タスクの優先度")
    due_date: Optional[date] = Field(None, description="期限")
    tags: list[str] = Field(default_factory=list, description="タグのリスト")
    created_time: datetime = Field(..., description="作成日時")
    last_edited_time: datetime = Field(..., description="最終更新日時")
    url: str = Field(..., description="NotionページのURL")

    model_config = ConfigDict(
        # Enumの値をそのまま使用
        use_enum_values=False
    )


class NotionPropertyValue(BaseModel):
    """Notionプロパティの値を表す汎用モデル.

    様々な型のプロパティ値を柔軟に扱うためのモデル。
    """

    type: str = Field(..., description="プロパティの型")
    value: Any = Field(..., description="プロパティの値")


class NotionPage(BaseModel):
    """Notionページの基本情報.

    Notion APIのページレスポンスを表現するモデル。
    """

    object: str = Field(..., description="オブジェクトタイプ（常に'page'）")
    id: str = Field(..., description="ページID")
    created_time: datetime = Field(..., description="作成日時")
    last_edited_time: datetime = Field(..., description="最終更新日時")
    archived: bool = Field(False, description="アーカイブ済みかどうか")
    properties: dict[str, Any] = Field(..., description="ページプロパティ")
    url: str = Field(..., description="ページURL")


class NotionDatabaseQueryResponse(BaseModel):
    """Notionデータベースクエリのレスポンス.

    データベースクエリAPIのレスポンスを表現するモデル。
    ページネーション情報を含みます。
    """

    object: str = Field(..., description="オブジェクトタイプ（常に'list'）")
    results: list[NotionPage] = Field(..., description="ページのリスト")
    next_cursor: Optional[str] = Field(None, description="次のページのカーソル")
    has_more: bool = Field(False, description="次のページが存在するか")


class NotionError(BaseModel):
    """Notion APIのエラーレスポンス.

    API呼び出しが失敗した際のエラー情報を表現するモデル。
    """

    object: str = Field(..., description="オブジェクトタイプ（常に'error'）")
    status: int = Field(..., description="HTTPステータスコード")
    code: str = Field(..., description="エラーコード")
    message: str = Field(..., description="エラーメッセージ")
