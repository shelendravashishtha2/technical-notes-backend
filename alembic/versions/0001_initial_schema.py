from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
    op.execute("create extension if not exists pg_trgm")
    op.execute("create extension if not exists unaccent")
    topic_status = postgresql.ENUM("draft","published","archived",name="topic_status",create_type=False)
    content_format = postgresql.ENUM("markdown","mdx","html",name="content_format",create_type=False)
    difficulty = postgresql.ENUM("beginner","intermediate","advanced","expert",name="difficulty",create_type=False)
    asset_kind = postgresql.ENUM("image","diagram","code","file","external_link",name="asset_kind",create_type=False)
    export_status = postgresql.ENUM("queued","running","completed","failed",name="export_status", create_type=False)
    topic_status.create(op.get_bind(), checkfirst=True)
    content_format.create(op.get_bind(), checkfirst=True)
    difficulty.create(op.get_bind(), checkfirst=True)
    asset_kind.create(op.get_bind(), checkfirst=True)
    export_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_groups_slug", "groups", ["slug"], unique=True)
    op.create_index("ix_groups_sort_order", "groups", ["sort_order"])

    op.create_table(
        "domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_domains_slug", "domains", ["slug"], unique=True)
    op.create_index("ix_domains_sort_order", "domains", ["sort_order"])

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"], unique=True)

    op.create_table(
        "note_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_note_collections_slug", "note_collections", ["slug"], unique=True)

    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("subtitle", sa.String(320)),
        sa.Column("summary", sa.Text()),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="SET NULL")),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id", ondelete="SET NULL")),
        sa.Column("parent_topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="SET NULL")),
        sa.Column("status", topic_status, nullable=False, server_default="published"),
        sa.Column("content_format", content_format, nullable=False, server_default="markdown"),
        sa.Column("difficulty", difficulty),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_plain_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("reading_time_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("section_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_checksum", sa.String(128)),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("extra_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("word_count >= 0", name="topic_word_count_non_negative"),
        sa.CheckConstraint("section_count >= 0", name="topic_section_count_non_negative"),
    )
    op.create_index("ix_topics_slug", "topics", ["slug"], unique=True)
    op.create_index("ix_topics_body_hash", "topics", ["body_hash"])
    op.create_index("ix_topics_status_order_slug", "topics", ["status", "order_index", "slug"])
    op.create_index("ix_topics_group_status_order", "topics", ["group_id", "status", "order_index"])
    op.create_index("ix_topics_domain_status_order", "topics", ["domain_id", "status", "order_index"])
    op.create_index("ix_topics_metadata_gin", "topics", ["metadata_json"], postgresql_using="gin")
    op.create_index("ix_topics_search_vector_gin", "topics", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_topics_title_trgm", "topics", ["title"], postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"})

    op.create_table(
        "topic_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_sections.id", ondelete="CASCADE")),
        sa.Column("slug", sa.String(240), nullable=False),
        sa.Column("anchor", sa.String(260), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("materialized_path", sa.String(1200), nullable=False, server_default=""),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_plain_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reading_time_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("level between 1 and 6", name="topic_section_level_valid"),
        sa.UniqueConstraint("topic_id", "slug", name="uq_topic_sections_topic_slug"),
        sa.UniqueConstraint("topic_id", "anchor", name="uq_topic_sections_topic_anchor"),
    )
    op.create_index("ix_topic_sections_topic_order", "topic_sections", ["topic_id", "order_index"])
    op.create_index("ix_topic_sections_search_vector_gin", "topic_sections", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_topic_sections_title_trgm", "topic_sections", ["title"], postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"})

    op.create_table("topic_tags", sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True), sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True))

    op.create_table(
        "source_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_key", sa.String(260), nullable=False),
        sa.Column("display_name", sa.String(320), nullable=False),
        sa.Column("path", sa.Text()),
        sa.Column("checksum", sa.String(128)),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_source_files_source_key", "source_files", ["source_key"], unique=True)
    op.create_index("ix_source_files_checksum", "source_files", ["checksum"])

    op.create_table("topic_source_links", sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True), sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_files.id", ondelete="CASCADE"), primary_key=True), sa.Column("relevance", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_key", sa.String(260), nullable=False),
        sa.Column("kind", asset_kind, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("storage_provider", sa.String(80)),
        sa.Column("alt_text", sa.Text()),
        sa.Column("checksum", sa.String(128)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_assets_asset_key", "assets", ["asset_key"], unique=True)

    op.create_table("topic_assets", sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True), sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True), sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topic_sections.id", ondelete="SET NULL")), sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))

    op.create_table("topic_collection_links", sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("note_collections.id", ondelete="CASCADE"), primary_key=True), sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True), sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "topic_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("change_note", sa.Text()),
        sa.Column("actor", sa.String(180)),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("topic_id", "version", name="uq_topic_revisions_topic_version"),
    )

    op.create_table(
        "search_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_id", sa.String(140)),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.create_index("ix_search_events_created_at", "search_events", ["created_at"])
    op.create_index("ix_search_events_query", "search_events", ["query"])

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_job_id", sa.String(180)),
        sa.Column("status", export_status, nullable=False, server_default="queued"),
        sa.Column("selection_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


    op.create_table(
        "content_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("batch_key", sa.String(180), nullable=False),
        sa.Column("source", sa.String(120), nullable=False, server_default="frontend-export"),
        sa.Column("status", sa.String(60), nullable=False, server_default="created"),
        sa.Column("stats_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_content_import_batches_batch_key", "content_import_batches", ["batch_key"], unique=True)
    op.create_index("ix_content_import_batches_status", "content_import_batches", ["status"])

    op.create_table(
        "saved_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("scope_label", sa.String(280)),
        sa.Column("selection_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_saved_selections_slug", "saved_selections", ["slug"], unique=True)
    op.create_index("ix_saved_selections_sort_order", "saved_selections", ["sort_order"])
    op.create_index("ix_saved_selections_is_default", "saved_selections", ["is_default"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor", sa.String(180), nullable=False, server_default="admin"),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(120), nullable=False),
        sa.Column("entity_id", sa.String(180)),
        sa.Column("request_id", sa.String(80)),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.execute(
        """
        create or replace function refresh_topic_search_vectors()
        returns void language plpgsql as $$
        begin
          update topics set search_vector =
            setweight(to_tsvector('english', unaccent(coalesce(title, ''))), 'A') ||
            setweight(to_tsvector('english', unaccent(coalesce(subtitle, ''))), 'A') ||
            setweight(to_tsvector('english', unaccent(coalesce(summary, ''))), 'B') ||
            setweight(to_tsvector('english', unaccent(coalesce(body_plain_text, ''))), 'C');

          update topic_sections set search_vector =
            setweight(to_tsvector('english', unaccent(coalesce(title, ''))), 'A') ||
            setweight(to_tsvector('english', unaccent(coalesce(body_plain_text, ''))), 'C');
        end;
        $$;
        """
    )

    op.execute(
        """
        create or replace function topics_search_vector_trigger()
        returns trigger language plpgsql as $$
        begin
          new.search_vector :=
            setweight(to_tsvector('english', unaccent(coalesce(new.title, ''))), 'A') ||
            setweight(to_tsvector('english', unaccent(coalesce(new.subtitle, ''))), 'A') ||
            setweight(to_tsvector('english', unaccent(coalesce(new.summary, ''))), 'B') ||
            setweight(to_tsvector('english', unaccent(coalesce(new.body_plain_text, ''))), 'C');
          return new;
        end;
        $$;

        create trigger trg_topics_search_vector
        before insert or update of title, subtitle, summary, body_plain_text
        on topics
        for each row execute function topics_search_vector_trigger();
        """
    )

    op.execute(
        """
        create or replace function sections_search_vector_trigger()
        returns trigger language plpgsql as $$
        begin
          new.search_vector :=
            setweight(to_tsvector('english', unaccent(coalesce(new.title, ''))), 'A') ||
            setweight(to_tsvector('english', unaccent(coalesce(new.body_plain_text, ''))), 'C');
          return new;
        end;
        $$;

        create trigger trg_topic_sections_search_vector
        before insert or update of title, body_plain_text
        on topic_sections
        for each row execute function sections_search_vector_trigger();
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_topic_sections_search_vector on topic_sections")
    op.execute("drop function if exists sections_search_vector_trigger")
    op.execute("drop trigger if exists trg_topics_search_vector on topics")
    op.execute("drop function if exists topics_search_vector_trigger")
    op.execute("drop function if exists refresh_topic_search_vectors")

    for table in [
        "audit_logs",
        "saved_selections",
        "content_import_batches",
        "export_jobs",
        "search_events",
        "topic_revisions",
        "topic_collection_links",
        "topic_assets",
        "assets",
        "topic_source_links",
        "source_files",
        "topic_tags",
        "topic_sections",
        "topics",
        "note_collections",
        "tags",
        "domains",
        "groups",
    ]:
        op.drop_table(table)

    for enum_name in ["export_status", "asset_kind", "difficulty", "content_format", "topic_status"]:
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
