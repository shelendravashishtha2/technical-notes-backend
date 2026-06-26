from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorPageInfo(BaseModel):
    limit: int
    has_next_page: bool
    next_cursor: str | None = None


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    page_info: CursorPageInfo


class OffsetPageInfo(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int | None = None
    has_next_page: bool


class OffsetPage(BaseModel, Generic[T]):
    items: list[T]
    page_info: OffsetPageInfo


class CursorRequest(BaseModel):
    limit: int = Field(default=30, ge=1, le=100)
    cursor: str | None = None
