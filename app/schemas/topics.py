from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.content import ContentFormat, Difficulty, TopicStatus


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class SourceOut(BaseModel):
    uuid: UUID
    source_key: str
    display_name: str
    path: str | None = None
    checksum: str | None = None
    mime_type: str | None = None

    @computed_field  # type: ignore[misc]
    @property
    def id(self) -> str:
        return self.source_key


class AssetOut(BaseModel):
    uuid: UUID
    asset_key: str
    kind: str
    url: str
    alt_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[misc]
    @property
    def id(self) -> str:
        return self.asset_key


class TopicSectionOut(BaseModel):
    """Frontend-compatible section shape.

    The React app's `getSections()` returns `{ id, title, level, rawText, plainText }`.
    The API returns the same stable keys so the frontend can build TOC/export trees
    without re-parsing full markdown for every topic.
    """

    uuid: UUID
    id: str
    slug: str
    anchor: str
    title: str
    level: int
    order_index: int
    materialized_path: str
    parent_id: str | None = None
    raw_text: str | None = None
    rawText: str | None = None
    plain_text: str | None = None
    plainText: str | None = None
    content: str | None = None
    body_markdown: str | None = None
    body_hash: str | None = None
    word_count: int
    reading_time_minutes: int
    children: list["TopicSectionOut"] = Field(default_factory=list)


class TopicListItem(BaseModel):
    """Lightweight topic card/nav record.

    `id` is intentionally the stable frontend id, not the DB UUID. The DB UUID is
    exposed separately as `uuid` for admin/debugging.
    """

    uuid: UUID
    id: str
    slug: str
    title: str
    subtitle: str | None = None
    summary: str | None = None
    group: str | None = None
    group_slug: str | None = None
    domain: str | None = None
    domain_slug: str | None = None
    difficulty: Difficulty | None = None
    status: TopicStatus
    order_index: int
    section_count: int
    word_count: int
    reading_time_minutes: int
    body_hash: str
    version: int
    is_featured: bool
    updated_at: datetime
    sourceFiles: list[str] = Field(default_factory=list)
    tags: list[TagOut] = Field(default_factory=list)
    sections: list[TopicSectionOut] = Field(default_factory=list)


class TopicDetail(TopicListItem):
    content_format: ContentFormat
    content: str
    body_markdown: str
    body_plain_text: str | None = None
    sources: list[SourceOut] = Field(default_factory=list)
    assets: list[AssetOut] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class TopicTreeNode(BaseModel):
    id: str
    slug: str
    title: str
    summary: str | None = None
    group: str | None = None
    group_slug: str | None = None
    domain: str | None = None
    domain_slug: str | None = None
    order_index: int
    section_count: int
    word_count: int
    body_hash: str
    version: int
    sourceFiles: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sections: list[TopicSectionOut] = Field(default_factory=list)
    children: list["TopicTreeNode"] = Field(default_factory=list)


class GroupedTopicTree(BaseModel):
    group: str
    group_slug: str | None = None
    sort_order: int = 0
    topics: list[TopicTreeNode]


class TopicBatchRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=100)
    slugs: list[str] = Field(default_factory=list, max_length=100)
    include_sections: bool = True
    include_sources: bool = True
    include_assets: bool = False
    include_section_bodies: bool = True

    @computed_field  # type: ignore[misc]
    @property
    def topic_ids(self) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in [*self.ids, *self.slugs]:
            key = value.strip()
            if key and key not in seen:
                seen.add(key)
                output.append(key)
        return output


class TopicCreate(BaseModel):
    id: str | None = Field(default=None, min_length=2, max_length=220)
    slug: str | None = Field(default=None, min_length=2, max_length=220)
    title: str = Field(min_length=2, max_length=280)
    subtitle: str | None = Field(default=None, max_length=320)
    summary: str | None = None
    group: str | None = None
    group_slug: str | None = None
    group_name: str | None = None
    domain: str | None = None
    domain_slug: str | None = None
    domain_name: str | None = None
    parent_topic_id: str | None = None
    parent_topic_slug: str | None = None
    status: TopicStatus = TopicStatus.published
    content_format: ContentFormat = ContentFormat.markdown
    difficulty: Difficulty | None = None
    content: str | None = None
    body_markdown: str | None = None
    sections: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sourceFiles: list[str] = Field(default_factory=list)
    source_keys: list[str] = Field(default_factory=list)
    order_index: int = 0
    is_featured: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[misc]
    @property
    def resolved_slug(self) -> str:
        return self.slug or self.id or ""

    @computed_field  # type: ignore[misc]
    @property
    def resolved_body_markdown(self) -> str:
        return self.body_markdown if self.body_markdown is not None else (self.content or "")

    @computed_field  # type: ignore[misc]
    @property
    def resolved_source_keys(self) -> list[str]:
        return [*self.source_keys, *self.sourceFiles]


class TopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=280)
    subtitle: str | None = Field(default=None, max_length=320)
    summary: str | None = None
    group: str | None = None
    group_slug: str | None = None
    group_name: str | None = None
    domain: str | None = None
    domain_slug: str | None = None
    domain_name: str | None = None
    parent_topic_id: str | None = None
    parent_topic_slug: str | None = None
    status: TopicStatus | None = None
    content_format: ContentFormat | None = None
    difficulty: Difficulty | None = None
    content: str | None = None
    body_markdown: str | None = None
    sections: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    sourceFiles: list[str] | None = None
    source_keys: list[str] | None = None
    order_index: int | None = None
    is_featured: bool | None = None
    metadata: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None
    change_note: str | None = None

    @computed_field  # type: ignore[misc]
    @property
    def resolved_body_markdown(self) -> str | None:
        return self.body_markdown if self.body_markdown is not None else self.content

    @computed_field  # type: ignore[misc]
    @property
    def resolved_source_keys(self) -> list[str] | None:
        if self.source_keys is None and self.sourceFiles is None:
            return None
        return [*(self.source_keys or []), *(self.sourceFiles or [])]


class TopicBulkUpsertRequest(BaseModel):
    mode: Literal["upsert", "insert_only", "update_only"] = "upsert"
    topics: list[TopicCreate] = Field(min_length=1, max_length=500)
