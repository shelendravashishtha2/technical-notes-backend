from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TopicStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class ContentFormat(str, enum.Enum):
    markdown = "markdown"
    mdx = "mdx"
    html = "html"


class Difficulty(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


class AssetKind(str, enum.Enum):
    image = "image"
    diagram = "diagram"
    code = "code"
    file = "file"
    external_link = "external_link"


class ExportStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Group(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "groups"

    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topics: Mapped[list[Topic]] = relationship(back_populates="group")


class Domain(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "domains"

    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topics: Mapped[list[Topic]] = relationship(back_populates="domain")


class Tag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tags"

    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topics: Mapped[list[TopicTag]] = relationship(back_populates="tag", cascade="all, delete-orphan")


class NoteCollection(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "note_collections"

    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topics: Mapped[list[TopicCollectionLink]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class Topic(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "topics"

    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(320))
    summary: Mapped[str | None] = mapped_column(Text)

    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("domains.id", ondelete="SET NULL"), index=True)
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[TopicStatus] = mapped_column(
        Enum(TopicStatus, name="topic_status"),
        default=TopicStatus.published,
        nullable=False,
        index=True,
    )
    content_format: Mapped[ContentFormat] = mapped_column(
        Enum(ContentFormat, name="content_format"),
        default=ContentFormat.markdown,
        nullable=False,
    )
    difficulty: Mapped[Difficulty | None] = mapped_column(Enum(Difficulty, name="difficulty"))

    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_plain_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)

    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    section_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    source_checksum: Mapped[str | None] = mapped_column(String(128), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    extra_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)

    group: Mapped[Group | None] = relationship(back_populates="topics")
    domain: Mapped[Domain | None] = relationship(back_populates="topics")
    parent: Mapped[Topic | None] = relationship(remote_side="Topic.id")
    sections: Mapped[list[TopicSection]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="TopicSection.order_index",
    )
    tags: Mapped[list[TopicTag]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    sources: Mapped[list[TopicSourceLink]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    assets: Mapped[list[TopicAsset]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    collections: Mapped[list[TopicCollectionLink]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    revisions: Mapped[list[TopicRevision]] = relationship(back_populates="topic")

    __table_args__ = (
        CheckConstraint("word_count >= 0", name="topic_word_count_non_negative"),
        CheckConstraint("section_count >= 0", name="topic_section_count_non_negative"),
        Index("ix_topics_status_order_slug", "status", "order_index", "slug"),
        Index("ix_topics_group_status_order", "group_id", "status", "order_index"),
        Index("ix_topics_domain_status_order", "domain_id", "status", "order_index"),
        Index("ix_topics_metadata_gin", "metadata_json", postgresql_using="gin"),
        Index("ix_topics_search_vector_gin", "search_vector", postgresql_using="gin"),
    )


class TopicSection(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "topic_sections"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topic_sections.id", ondelete="CASCADE"), index=True
    )

    slug: Mapped[str] = mapped_column(String(240), nullable=False)
    anchor: Mapped[str] = mapped_column(String(260), nullable=False)
    title: Mapped[str] = mapped_column(String(320), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    materialized_path: Mapped[str] = mapped_column(String(1200), default="", nullable=False, index=True)

    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_plain_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)

    topic: Mapped[Topic] = relationship(back_populates="sections")
    parent: Mapped[TopicSection | None] = relationship(remote_side="TopicSection.id")

    __table_args__ = (
        UniqueConstraint("topic_id", "slug", name="uq_topic_sections_topic_slug"),
        UniqueConstraint("topic_id", "anchor", name="uq_topic_sections_topic_anchor"),
        CheckConstraint("level between 1 and 6", name="topic_section_level_valid"),
        Index("ix_topic_sections_topic_order", "topic_id", "order_index"),
        Index("ix_topic_sections_search_vector_gin", "search_vector", postgresql_using="gin"),
    )


class TopicTag(Base):
    __tablename__ = "topic_tags"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    topic: Mapped[Topic] = relationship(back_populates="tags")
    tag: Mapped[Tag] = relationship(back_populates="topics")


class SourceFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_files"

    source_key: Mapped[str] = mapped_column(String(260), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(320), nullable=False)
    path: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(128), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topics: Mapped[list[TopicSourceLink]] = relationship(back_populates="source")


class TopicSourceLink(Base):
    __tablename__ = "topic_source_links"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"), primary_key=True
    )
    relevance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="sources")
    source: Mapped[SourceFile] = relationship(back_populates="topics")


class Asset(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "assets"

    asset_key: Mapped[str] = mapped_column(String(260), unique=True, index=True, nullable=False)
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind, name="asset_kind"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_provider: Mapped[str | None] = mapped_column(String(80))
    alt_text: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(128), index=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topics: Mapped[list[TopicAsset]] = relationship(back_populates="asset")


class TopicAsset(Base):
    __tablename__ = "topic_assets"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topic_sections.id", ondelete="SET NULL"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="assets")
    asset: Mapped[Asset] = relationship(back_populates="topics")


class TopicCollectionLink(Base):
    __tablename__ = "topic_collection_links"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("note_collections.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)

    collection: Mapped[NoteCollection] = relationship(back_populates="topics")
    topic: Mapped[Topic] = relationship(back_populates="collections")


class TopicRevision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "topic_revisions"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    change_note: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(String(180))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="revisions")

    __table_args__ = (UniqueConstraint("topic_id", "version", name="uq_topic_revisions_topic_version"),)


class SearchEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "search_events"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(140), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ExportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "export_jobs"

    client_job_id: Mapped[str | None] = mapped_column(String(180), index=True)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status"), default=ExportStatus.queued, nullable=False, index=True
    )
    selection_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(180), default="admin", nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(180), index=True)
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(80))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ContentImportBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "content_import_batches"

    batch_key: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="frontend-export", nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="created", nullable=False, index=True)
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class SavedSelection(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "saved_selections"

    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    scope_label: Mapped[str | None] = mapped_column(String(280))
    selection_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class AppCache(Base):
    __tablename__ = "app_cache"

    cache_key: Mapped[str] = mapped_column(String(220), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    etag: Mapped[str] = mapped_column(String(96), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_app_cache_updated_at", "updated_at"),
    )
