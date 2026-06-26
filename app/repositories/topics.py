from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import Select, delete, func, select, text, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import (
    Domain,
    Group,
    SourceFile,
    Tag,
    Topic,
    TopicAsset,
    TopicRevision,
    TopicSection,
    TopicSourceLink,
    TopicStatus,
    TopicTag,
)
from app.schemas.pagination import CursorPage, CursorPageInfo
from app.schemas.topics import (
    AssetOut,
    SourceOut,
    TagOut,
    TopicCreate,
    TopicDetail,
    TopicListItem,
    TopicSectionOut,
    TopicUpdate,
)
from app.utils.http import decode_cursor, encode_cursor
from app.utils.text import (
    markdown_to_plain_text,
    parse_markdown_sections,
    reading_minutes,
    sha256_text,
    slugify,
    word_count,
)


DEFAULT_GROUP_ORDER = [
    "AWS",
    "Python",
    "Flask",
    "FastAPI",
    "JavaScript",
    "React",
    "Redux",
    "CSS",
    "TypeScript",
    "Frontend Concepts",
    "Backend Concepts",
    "Databases",
    "DevOps",
    "GenAI",
    "Reference",
    "Start Here",
    "Practice Plan",
    "Interview Q&A",
    "Architecture",
]


def _source_files(topic: Topic) -> list[str]:
    return [link.source.source_key for link in sorted(topic.sources, key=lambda link: link.relevance)]


def _tag_out(link: TopicTag) -> TagOut:
    return TagOut(slug=link.tag.slug, name=link.tag.name)


def _section_raw_text(section: TopicSection) -> str:
    heading = f"{'#' * section.level} {section.title}".strip()
    body = section.body_markdown.strip()
    return f"{heading}\n\n{body}".strip() if body else heading


def _section_out(section: TopicSection, include_body: bool = False) -> TopicSectionOut:
    raw_text = _section_raw_text(section) if include_body else None
    return TopicSectionOut(
        uuid=section.id,
        id=section.slug,
        slug=section.slug,
        anchor=section.anchor,
        title=section.title,
        level=section.level,
        order_index=section.order_index,
        parent_id=str(section.parent_section_id) if section.parent_section_id else None,
        materialized_path=section.materialized_path,
        raw_text=raw_text,
        rawText=raw_text,
        plain_text=section.body_plain_text if include_body else None,
        plainText=section.body_plain_text if include_body else None,
        content=raw_text,
        body_markdown=section.body_markdown if include_body else None,
        body_hash=section.body_hash,
        word_count=section.word_count,
        reading_time_minutes=section.reading_time_minutes,
        children=[],
    )


def build_section_outline(sections: list[TopicSection], *, include_body: bool = False) -> list[TopicSectionOut]:
    return [
        _section_out(section, include_body=include_body)
        for section in sorted(sections, key=lambda item: item.order_index)
        if section.deleted_at is None
    ]


def topic_to_list_item(topic: Topic, *, include_sections: bool = True) -> TopicListItem:
    return TopicListItem(
        uuid=topic.id,
        id=topic.slug,
        slug=topic.slug,
        title=topic.title,
        subtitle=topic.subtitle,
        summary=topic.summary,
        group=topic.group.name if topic.group else None,
        group_slug=topic.group.slug if topic.group else None,
        domain=topic.domain.name if topic.domain else None,
        domain_slug=topic.domain.slug if topic.domain else None,
        difficulty=topic.difficulty,
        status=topic.status,
        order_index=topic.order_index,
        section_count=topic.section_count,
        word_count=topic.word_count,
        reading_time_minutes=topic.reading_time_minutes,
        body_hash=topic.body_hash,
        version=topic.version,
        is_featured=topic.is_featured,
        updated_at=topic.updated_at,
        sourceFiles=_source_files(topic),
        tags=[_tag_out(link) for link in topic.tags],
        sections=build_section_outline(topic.sections, include_body=False) if include_sections else [],
    )


def topic_to_detail(
    topic: Topic,
    *,
    include_sections: bool = True,
    include_sources: bool = True,
    include_assets: bool = True,
    include_section_bodies: bool = True,
) -> TopicDetail:
    list_item = topic_to_list_item(topic, include_sections=False)
    sources: list[SourceOut] = []
    if include_sources:
        sources = [
            SourceOut(
                uuid=link.source.id,
                source_key=link.source.source_key,
                display_name=link.source.display_name,
                path=link.source.path,
                checksum=link.source.checksum,
                mime_type=link.source.mime_type,
            )
            for link in sorted(topic.sources, key=lambda link: link.relevance)
        ]

    assets: list[AssetOut] = []
    if include_assets:
        assets = [
            AssetOut(
                uuid=link.asset.id,
                asset_key=link.asset.asset_key,
                kind=link.asset.kind.value,
                url=link.asset.url,
                alt_text=link.asset.alt_text,
                metadata=link.asset.metadata_json,
            )
            for link in sorted(topic.assets, key=lambda link: link.order_index)
        ]

    return TopicDetail(
        **list_item.model_dump(exclude={"sections"}),
        content_format=topic.content_format,
        content=topic.body_markdown,
        body_markdown=topic.body_markdown,
        body_plain_text=topic.body_plain_text,
        sections=build_section_outline(topic.sections, include_body=include_section_bodies)
        if include_sections
        else [],
        sources=sources,
        assets=assets,
        metadata=topic.metadata_json,
        extra=topic.extra_json,
    )


class TopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_topic_query(self, *, include_sections: bool = True) -> Select[tuple[Topic]]:
        options = [
            selectinload(Topic.group),
            selectinload(Topic.domain),
            selectinload(Topic.tags).selectinload(TopicTag.tag),
            selectinload(Topic.sources).selectinload(TopicSourceLink.source),
        ]
        if include_sections:
            options.append(selectinload(Topic.sections))
        return select(Topic).where(Topic.deleted_at.is_(None)).options(*options)

    async def list_topics(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        group: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        status: TopicStatus = TopicStatus.published,
        featured: bool | None = None,
        include_sections: bool = True,
    ) -> CursorPage[TopicListItem]:
        stmt = self._base_topic_query(include_sections=include_sections).where(Topic.status == status)

        if group:
            stmt = stmt.join(Topic.group).where(Group.slug == group)
        if domain:
            stmt = stmt.join(Topic.domain).where(Domain.slug == domain)
        if tag:
            stmt = stmt.join(Topic.tags).join(TopicTag.tag).where(Tag.slug == tag)
        if featured is not None:
            stmt = stmt.where(Topic.is_featured == featured)

        decoded = decode_cursor(cursor)
        if decoded:
            order_index = int(decoded.get("order_index", 0))
            slug = str(decoded.get("slug", ""))
            stmt = stmt.where(tuple_(Topic.order_index, Topic.slug) > tuple_(order_index, slug))

        stmt = stmt.order_by(Topic.order_index.asc(), Topic.slug.asc()).limit(limit + 1)
        topics = list((await self.session.scalars(stmt)).unique())
        has_next = len(topics) > limit
        visible = topics[:limit]
        next_cursor = None
        if has_next and visible:
            last = visible[-1]
            next_cursor = encode_cursor({"order_index": last.order_index, "slug": last.slug})

        return CursorPage(
            items=[topic_to_list_item(topic, include_sections=include_sections) for topic in visible],
            page_info=CursorPageInfo(limit=limit, has_next_page=has_next, next_cursor=next_cursor),
        )

    async def get_topic_detail(
        self,
        slug: str,
        *,
        include_sections: bool = True,
        include_sources: bool = True,
        include_assets: bool = True,
        include_section_bodies: bool = True,
        status: TopicStatus | None = TopicStatus.published,
    ) -> TopicDetail | None:
        stmt = (
            select(Topic)
            .where(Topic.slug == slug, Topic.deleted_at.is_(None))
            .options(
                selectinload(Topic.group),
                selectinload(Topic.domain),
                selectinload(Topic.sections),
                selectinload(Topic.tags).selectinload(TopicTag.tag),
                selectinload(Topic.sources).selectinload(TopicSourceLink.source),
                selectinload(Topic.assets).selectinload(TopicAsset.asset),
            )
        )
        if status is not None:
            stmt = stmt.where(Topic.status == status)
        topic = (await self.session.scalars(stmt)).unique().one_or_none()
        if not topic:
            return None
        return topic_to_detail(
            topic,
            include_sections=include_sections,
            include_sources=include_sources,
            include_assets=include_assets,
            include_section_bodies=include_section_bodies,
        )

    async def batch_get_topics(
        self,
        slugs: list[str],
        *,
        include_sections: bool = True,
        include_sources: bool = True,
        include_assets: bool = False,
        include_section_bodies: bool = True,
    ) -> list[TopicDetail]:
        slugs = [slug.strip() for slug in slugs if slug.strip()]
        if not slugs:
            return []

        stmt = (
            select(Topic)
            .where(Topic.slug.in_(slugs), Topic.deleted_at.is_(None), Topic.status == TopicStatus.published)
            .options(
                selectinload(Topic.group),
                selectinload(Topic.domain),
                selectinload(Topic.sections),
                selectinload(Topic.tags).selectinload(TopicTag.tag),
                selectinload(Topic.sources).selectinload(TopicSourceLink.source),
                selectinload(Topic.assets).selectinload(TopicAsset.asset),
            )
        )
        topics = list((await self.session.scalars(stmt)).unique())
        by_slug = {topic.slug: topic for topic in topics}
        ordered = [by_slug[slug] for slug in slugs if slug in by_slug]
        return [
            topic_to_detail(
                topic,
                include_sections=include_sections,
                include_sources=include_sources,
                include_assets=include_assets,
                include_section_bodies=include_section_bodies,
            )
            for topic in ordered
        ]


    async def get_topic_detail_payload_fast(
        self,
        slug: str,
        *,
        include_sections: bool = True,
        include_sources: bool = True,
        include_section_bodies: bool = True,
    ) -> dict[str, Any] | None:
        """Fast JSON-ready topic detail without ORM relationship hydration."""
        topic_stmt = text("""
            SELECT
                t.id::text AS uuid,
                t.slug AS id,
                t.slug,
                t.title,
                t.subtitle,
                t.summary,
                g.name AS "group",
                g.slug AS group_slug,
                d.name AS domain,
                d.slug AS domain_slug,
                t.difficulty::text AS difficulty,
                t.status::text AS status,
                t.content_format::text AS content_format,
                t.order_index,
                t.section_count,
                t.word_count,
                t.reading_time_minutes,
                t.body_hash,
                t.version,
                t.is_featured,
                t.updated_at,
                t.body_markdown,
                t.body_plain_text,
                t.metadata_json,
                t.extra_json
            FROM topics t
            LEFT JOIN groups g ON g.id = t.group_id
            LEFT JOIN domains d ON d.id = t.domain_id
            WHERE t.slug = :slug
              AND t.deleted_at IS NULL
              AND t.status = 'published'
            LIMIT 1
        """)
        row = (await self.session.execute(topic_stmt, {"slug": slug})).mappings().one_or_none()
        if not row:
            return None

        updated_at = row["updated_at"]
        payload: dict[str, Any] = {
            "uuid": row["uuid"],
            "id": row["id"],
            "slug": row["slug"],
            "title": row["title"],
            "subtitle": row["subtitle"],
            "summary": row["summary"],
            "group": row["group"],
            "group_slug": row["group_slug"],
            "domain": row["domain"],
            "domain_slug": row["domain_slug"],
            "difficulty": row["difficulty"],
            "status": row["status"],
            "content_format": row["content_format"],
            "order_index": row["order_index"],
            "section_count": row["section_count"],
            "word_count": row["word_count"],
            "reading_time_minutes": row["reading_time_minutes"],
            "body_hash": row["body_hash"],
            "content_hash": row["body_hash"],
            "version": row["version"],
            "is_featured": row["is_featured"],
            "updated_at": updated_at.isoformat().replace("+00:00", "Z") if updated_at else None,
            "content": row["body_markdown"],
            "body_markdown": row["body_markdown"],
            "body_plain_text": row["body_plain_text"],
            "metadata": row["metadata_json"] or {},
            "extra": row["extra_json"] or {},
            "sourceFiles": [],
            "tags": [],
            "sources": [],
            "assets": [],
            "sections": [],
        }

        if include_sources:
            source_stmt = text("""
                SELECT
                    sf.id::text AS uuid,
                    sf.source_key,
                    sf.display_name,
                    sf.path,
                    sf.checksum,
                    sf.mime_type
                FROM topic_source_links tsl
                JOIN source_files sf ON sf.id = tsl.source_id
                JOIN topics t ON t.id = tsl.topic_id
                WHERE t.slug = :slug
                ORDER BY tsl.relevance ASC, sf.source_key ASC
            """)
            source_rows = (await self.session.execute(source_stmt, {"slug": slug})).mappings().all()
            payload["sourceFiles"] = [r["source_key"] for r in source_rows]
            payload["sources"] = [
                {
                    "uuid": r["uuid"],
                    "id": r["source_key"],
                    "source_key": r["source_key"],
                    "display_name": r["display_name"],
                    "path": r["path"],
                    "checksum": r["checksum"],
                    "mime_type": r["mime_type"],
                }
                for r in source_rows
            ]

        if include_sections:
            section_stmt = text("""
                SELECT
                    s.id::text AS uuid,
                    s.slug AS id,
                    s.slug,
                    s.anchor,
                    s.title,
                    s.level,
                    s.order_index,
                    s.parent_section_id::text AS parent_id,
                    s.materialized_path,
                    CASE WHEN :include_bodies THEN s.body_markdown ELSE NULL END AS body_markdown,
                    CASE WHEN :include_bodies THEN s.body_plain_text ELSE NULL END AS plain_text,
                    s.body_hash,
                    s.word_count,
                    s.reading_time_minutes
                FROM topic_sections s
                JOIN topics t ON t.id = s.topic_id
                WHERE t.slug = :slug
                  AND s.deleted_at IS NULL
                ORDER BY s.order_index ASC
            """)
            section_rows = (
                await self.session.execute(
                    section_stmt,
                    {"slug": slug, "include_bodies": include_section_bodies},
                )
            ).mappings().all()
            sections = []
            for r in section_rows:
                body = r["body_markdown"]
                raw_text = None
                if include_section_bodies:
                    heading = f"{'#' * int(r['level'])} {r['title']}"
                    raw_text = f"{heading}\n\n{body}".strip() if body else heading
                sections.append(
                    {
                        "uuid": r["uuid"],
                        "id": r["id"],
                        "slug": r["slug"],
                        "anchor": r["anchor"],
                        "title": r["title"],
                        "level": r["level"],
                        "order_index": r["order_index"],
                        "materialized_path": r["materialized_path"],
                        "parent_id": r["parent_id"],
                        "raw_text": raw_text,
                        "rawText": raw_text,
                        "plain_text": r["plain_text"],
                        "plainText": r["plain_text"],
                        "content": raw_text,
                        "body_markdown": body,
                        "body_hash": r["body_hash"],
                        "word_count": r["word_count"],
                        "reading_time_minutes": r["reading_time_minutes"],
                        "children": [],
                    }
                )
            payload["sections"] = sections

        return payload

    async def list_grouped_tree(self) -> list[dict[str, Any]]:
        stmt = (
            self._base_topic_query(include_sections=True)
            .outerjoin(Topic.group)
            .where(Topic.status == TopicStatus.published)
            .order_by(Group.sort_order.asc().nulls_last(), Topic.order_index.asc(), Topic.slug.asc())
        )
        topics = list((await self.session.scalars(stmt)).unique())
        grouped: dict[str, list[Topic]] = defaultdict(list)
        group_meta: dict[str, tuple[str | None, int]] = {}
        for topic in topics:
            name = topic.group.name if topic.group else "Reference"
            grouped[name].append(topic)
            group_meta[name] = (topic.group.slug if topic.group else None, topic.group.sort_order if topic.group else 999)

        output: list[dict[str, Any]] = []
        for group_name, group_topics in grouped.items():
            nodes = []
            for topic in group_topics:
                nodes.append(
                    {
                        "id": topic.slug,
                        "slug": topic.slug,
                        "title": topic.title,
                        "summary": topic.summary,
                        "group": group_name,
                        "group_slug": topic.group.slug if topic.group else None,
                        "domain": topic.domain.name if topic.domain else None,
                        "domain_slug": topic.domain.slug if topic.domain else None,
                        "order_index": topic.order_index,
                        "section_count": topic.section_count,
                        "word_count": topic.word_count,
                        "body_hash": topic.body_hash,
                        "version": topic.version,
                        "sourceFiles": _source_files(topic),
                        "tags": [link.tag.slug for link in topic.tags],
                        "sections": [item.model_dump(mode="json") for item in build_section_outline(topic.sections)],
                        "children": [],
                    }
                )
            group_slug, sort_order = group_meta[group_name]
            output.append(
                {"group": group_name, "group_slug": group_slug, "sort_order": sort_order, "topics": nodes}
            )
        return sorted(output, key=lambda item: (item["sort_order"], item["group"]))

    async def count_stats(self) -> dict[str, int | str | list[str]]:
        topic_count = await self.session.scalar(
            select(func.count(Topic.id)).where(Topic.status == TopicStatus.published, Topic.deleted_at.is_(None))
        )
        section_count = await self.session.scalar(
            select(func.count(TopicSection.id)).where(TopicSection.deleted_at.is_(None))
        )
        tag_count = await self.session.scalar(select(func.count(Tag.id)))
        max_updated = await self.session.scalar(select(func.max(Topic.updated_at)))
        group_names = list(
            (
                await self.session.execute(
                    select(Group.name).order_by(Group.sort_order.asc(), Group.name.asc())
                )
            ).scalars()
        )
        group_order = group_names or DEFAULT_GROUP_ORDER
        return {
            "topic_count": int(topic_count or 0),
            "section_count": int(section_count or 0),
            "tag_count": int(tag_count or 0),
            "content_version": max_updated.isoformat() if max_updated else "empty",
            "group_order_preference": group_order,
        }

    async def get_or_create_group(self, slug: str | None, name: str | None) -> Group | None:
        if not slug and not name:
            return None
        slug = slug or slugify(name or "group")
        group = await self.session.scalar(select(Group).where(Group.slug == slug))
        if group:
            return group
        group = Group(slug=slug, name=name or slug.replace("-", " ").title())
        self.session.add(group)
        await self.session.flush()
        return group

    async def get_or_create_domain(self, slug: str | None, name: str | None) -> Domain | None:
        if not slug and not name:
            return None
        slug = slug or slugify(name or "domain")
        domain = await self.session.scalar(select(Domain).where(Domain.slug == slug))
        if domain:
            return domain
        domain = Domain(slug=slug, name=name or slug.replace("-", " ").title())
        self.session.add(domain)
        await self.session.flush()
        return domain

    async def _replace_tags(self, topic: Topic, tags: list[str]) -> None:
        await self.session.execute(delete(TopicTag).where(TopicTag.topic_id == topic.id))
        seen: set[str] = set()
        for raw in tags:
            tag_slug = slugify(raw)
            if not tag_slug or tag_slug in seen:
                continue
            seen.add(tag_slug)
            tag = await self.session.scalar(select(Tag).where(Tag.slug == tag_slug))
            if not tag:
                tag = Tag(slug=tag_slug, name=raw.strip() or tag_slug.replace("-", " ").title())
                self.session.add(tag)
                await self.session.flush()
            self.session.add(TopicTag(topic_id=topic.id, tag_id=tag.id))

    async def _replace_sources(self, topic: Topic, source_keys: list[str]) -> None:
        await self.session.execute(delete(TopicSourceLink).where(TopicSourceLink.topic_id == topic.id))
        seen: set[str] = set()
        for index, raw in enumerate(source_keys):
            source_key = raw.strip()
            if not source_key or source_key in seen:
                continue
            seen.add(source_key)
            source = await self.session.scalar(select(SourceFile).where(SourceFile.source_key == source_key))
            if not source:
                source = SourceFile(source_key=source_key, display_name=source_key)
                self.session.add(source)
                await self.session.flush()
            self.session.add(TopicSourceLink(topic_id=topic.id, source_id=source.id, relevance=index))

    async def _replace_sections(self, topic: Topic, explicit_sections: list[dict[str, Any]] | None) -> None:
        await self.session.execute(delete(TopicSection).where(TopicSection.topic_id == topic.id))
        parsed = parse_markdown_sections(topic.body_markdown) if explicit_sections is None else None
        created_by_order: dict[int, TopicSection] = {}

        if explicit_sections is not None:
            normalized = []
            for index, item in enumerate(explicit_sections):
                title = str(item.get("title") or f"Section {index + 1}")
                level = int(item.get("level") or 2)
                raw_text = str(item.get("rawText") or item.get("raw_text") or item.get("content") or item.get("body_markdown") or "")
                body = raw_text
                if raw_text.startswith("#"):
                    lines = raw_text.splitlines()
                    body = "\n".join(lines[1:]).strip()
                plain = markdown_to_plain_text(f"{title}\n{body}")
                words = word_count(plain)
                normalized.append(
                    {
                        "slug": item.get("id") or item.get("slug") or slugify(title, fallback=f"section-{index+1}"),
                        "anchor": item.get("anchor") or item.get("id") or item.get("slug") or f"section-{index+1}",
                        "title": title,
                        "level": level,
                        "order_index": int(item.get("order_index") or item.get("orderIndex") or index),
                        "parent_order_index": item.get("parent_order_index"),
                        "materialized_path": str(item.get("materialized_path") or item.get("materializedPath") or f"{index:04d}"),
                        "body_markdown": body,
                        "body_plain_text": plain,
                        "body_hash": sha256_text(f"{title}\n{body}"),
                        "word_count": words,
                        "reading_time_minutes": reading_minutes(words),
                        "metadata_json": item.get("metadata") or {},
                    }
                )
        else:
            normalized = [section.__dict__ for section in parsed or []]

        for item in sorted(normalized, key=lambda value: value["order_index"]):
            parent_id = None
            parent_order = item.get("parent_order_index")
            if parent_order is not None and parent_order in created_by_order:
                parent_id = created_by_order[parent_order].id
            section = TopicSection(
                topic_id=topic.id,
                parent_section_id=parent_id,
                slug=item["slug"],
                anchor=item["anchor"],
                title=item["title"],
                level=item["level"],
                order_index=item["order_index"],
                materialized_path=item["materialized_path"],
                body_markdown=item["body_markdown"],
                body_plain_text=item["body_plain_text"],
                body_hash=item["body_hash"],
                word_count=item["word_count"],
                reading_time_minutes=item["reading_time_minutes"],
                metadata_json=item.get("metadata_json") or {},
            )
            self.session.add(section)
            await self.session.flush()
            created_by_order[section.order_index] = section

        topic.section_count = len(normalized)


    async def upsert_topic_slim(self, payload: TopicCreate, *, mode: str = "upsert", actor: str = "admin") -> dict[str, str]:
        """Create/update a topic without hydrating and returning full detail.

        This is used by the high-throughput import path. The old admin import
        endpoint returned full TopicDetail objects per topic, which is very slow
        for large markdown bodies and thousands of sections.
        """
        resolved_slug = payload.resolved_slug or slugify(payload.title)
        existing = await self.session.scalar(
            select(Topic).where(Topic.slug == resolved_slug, Topic.deleted_at.is_(None))
        )
        if existing and mode == "insert_only":
            return {"action": "skipped", "slug": resolved_slug}
        if not existing and mode == "update_only":
            return {"action": "skipped", "slug": resolved_slug}
        if existing:
            update_payload = TopicUpdate(
                **payload.model_dump(exclude={"resolved_slug", "resolved_body_markdown", "resolved_source_keys"})
            )
            await self.update_topic_slim(existing, update_payload, actor=actor)
            return {"action": "updated", "slug": resolved_slug}
        await self.create_topic_slim(payload, actor=actor)
        return {"action": "created", "slug": resolved_slug}

    async def create_topic_slim(self, payload: TopicCreate, *, actor: str = "admin") -> Topic:
        resolved_slug = payload.resolved_slug or slugify(payload.title)
        group_name = payload.group_name or payload.group
        group_slug = payload.group_slug or (slugify(group_name) if group_name else None)
        group = await self.get_or_create_group(group_slug, group_name)
        domain_name = payload.domain_name or payload.domain
        domain_slug = payload.domain_slug or (slugify(domain_name) if domain_name else None)
        domain = await self.get_or_create_domain(domain_slug, domain_name)
        parent_slug = payload.parent_topic_slug or payload.parent_topic_id
        parent = None
        if parent_slug:
            parent = await self.session.scalar(select(Topic).where(Topic.slug == parent_slug))

        body_markdown = payload.resolved_body_markdown
        plain = markdown_to_plain_text(body_markdown)
        words = word_count(plain)
        topic = Topic(
            slug=resolved_slug,
            title=payload.title,
            subtitle=payload.subtitle,
            summary=payload.summary,
            group_id=group.id if group else None,
            domain_id=domain.id if domain else None,
            parent_topic_id=parent.id if parent else None,
            status=payload.status,
            content_format=payload.content_format,
            difficulty=payload.difficulty,
            body_markdown=body_markdown,
            body_plain_text=plain,
            body_hash=sha256_text(body_markdown),
            word_count=words,
            reading_time_minutes=reading_minutes(words),
            order_index=payload.order_index,
            is_featured=payload.is_featured,
            metadata_json=payload.metadata,
            extra_json=payload.extra,
        )
        self.session.add(topic)
        await self.session.flush()
        await self._replace_sections(topic, payload.sections if payload.sections else None)
        await self._replace_tags(topic, payload.tags)
        await self._replace_sources(topic, payload.resolved_source_keys)
        self.session.add(
            TopicRevision(
                topic_id=topic.id,
                version=topic.version,
                title=topic.title,
                summary=topic.summary,
                body_markdown=topic.body_markdown,
                body_hash=topic.body_hash,
                change_note="Initial create",
                actor=actor,
            )
        )
        await self.session.flush()
        return topic

    async def update_topic_slim(self, topic: Topic, payload: TopicUpdate, *, actor: str = "admin") -> Topic:
        if payload.title is not None:
            topic.title = payload.title
        if payload.subtitle is not None:
            topic.subtitle = payload.subtitle
        if payload.summary is not None:
            topic.summary = payload.summary
        if payload.status is not None:
            topic.status = payload.status
        if payload.content_format is not None:
            topic.content_format = payload.content_format
        if payload.difficulty is not None:
            topic.difficulty = payload.difficulty
        if payload.order_index is not None:
            topic.order_index = payload.order_index
        if payload.is_featured is not None:
            topic.is_featured = payload.is_featured
        if payload.metadata is not None:
            topic.metadata_json = payload.metadata
        if payload.extra is not None:
            topic.extra_json = payload.extra
        if payload.group_slug or payload.group_name or payload.group:
            group_name = payload.group_name or payload.group
            group_slug = payload.group_slug or (slugify(group_name) if group_name else None)
            group = await self.get_or_create_group(group_slug, group_name)
            topic.group_id = group.id if group else None
        if payload.domain_slug or payload.domain_name or payload.domain:
            domain_name = payload.domain_name or payload.domain
            domain_slug = payload.domain_slug or (slugify(domain_name) if domain_name else None)
            domain = await self.get_or_create_domain(domain_slug, domain_name)
            topic.domain_id = domain.id if domain else None
        parent_slug = payload.parent_topic_slug or payload.parent_topic_id
        if parent_slug is not None:
            parent = await self.session.scalar(select(Topic).where(Topic.slug == parent_slug))
            topic.parent_topic_id = parent.id if parent else None

        next_body = payload.resolved_body_markdown
        body_changed = next_body is not None and next_body != topic.body_markdown
        if body_changed:
            topic.body_markdown = next_body or ""
            topic.body_plain_text = markdown_to_plain_text(topic.body_markdown)
            topic.body_hash = sha256_text(topic.body_markdown)
            topic.word_count = word_count(topic.body_plain_text)
            topic.reading_time_minutes = reading_minutes(topic.word_count)
            topic.version += 1

        if payload.sections is not None or body_changed:
            await self._replace_sections(topic, payload.sections)
        if payload.tags is not None:
            await self._replace_tags(topic, payload.tags)
        if payload.resolved_source_keys is not None:
            await self._replace_sources(topic, payload.resolved_source_keys)

        if body_changed:
            self.session.add(
                TopicRevision(
                    topic_id=topic.id,
                    version=topic.version,
                    title=topic.title,
                    summary=topic.summary,
                    body_markdown=topic.body_markdown,
                    body_hash=topic.body_hash,
                    change_note=payload.change_note,
                    actor=actor,
                )
            )
        await self.session.flush()
        return topic

    async def create_topic(self, payload: TopicCreate, *, actor: str = "admin") -> TopicDetail:
        resolved_slug = payload.resolved_slug or slugify(payload.title)
        group_name = payload.group_name or payload.group
        group_slug = payload.group_slug or (slugify(group_name) if group_name else None)
        group = await self.get_or_create_group(group_slug, group_name)
        domain_name = payload.domain_name or payload.domain
        domain_slug = payload.domain_slug or (slugify(domain_name) if domain_name else None)
        domain = await self.get_or_create_domain(domain_slug, domain_name)
        parent_slug = payload.parent_topic_slug or payload.parent_topic_id
        parent = None
        if parent_slug:
            parent = await self.session.scalar(select(Topic).where(Topic.slug == parent_slug))

        body_markdown = payload.resolved_body_markdown
        plain = markdown_to_plain_text(body_markdown)
        words = word_count(plain)
        topic = Topic(
            slug=resolved_slug,
            title=payload.title,
            subtitle=payload.subtitle,
            summary=payload.summary,
            group_id=group.id if group else None,
            domain_id=domain.id if domain else None,
            parent_topic_id=parent.id if parent else None,
            status=payload.status,
            content_format=payload.content_format,
            difficulty=payload.difficulty,
            body_markdown=body_markdown,
            body_plain_text=plain,
            body_hash=sha256_text(body_markdown),
            word_count=words,
            reading_time_minutes=reading_minutes(words),
            order_index=payload.order_index,
            is_featured=payload.is_featured,
            metadata_json=payload.metadata,
            extra_json=payload.extra,
        )
        self.session.add(topic)
        await self.session.flush()
        await self._replace_sections(topic, payload.sections if payload.sections else None)
        await self._replace_tags(topic, payload.tags)
        await self._replace_sources(topic, payload.resolved_source_keys)
        self.session.add(
            TopicRevision(
                topic_id=topic.id,
                version=topic.version,
                title=topic.title,
                summary=topic.summary,
                body_markdown=topic.body_markdown,
                body_hash=topic.body_hash,
                change_note="Initial create",
                actor=actor,
            )
        )
        await self.session.flush()
        return await self.get_topic_detail(topic.slug, status=None)  # type: ignore[return-value]

    async def update_topic(self, slug: str, payload: TopicUpdate, *, actor: str = "admin") -> TopicDetail | None:
        topic = await self.session.scalar(select(Topic).where(Topic.slug == slug, Topic.deleted_at.is_(None)))
        if not topic:
            return None

        if payload.title is not None:
            topic.title = payload.title
        if payload.subtitle is not None:
            topic.subtitle = payload.subtitle
        if payload.summary is not None:
            topic.summary = payload.summary
        if payload.status is not None:
            topic.status = payload.status
        if payload.content_format is not None:
            topic.content_format = payload.content_format
        if payload.difficulty is not None:
            topic.difficulty = payload.difficulty
        if payload.order_index is not None:
            topic.order_index = payload.order_index
        if payload.is_featured is not None:
            topic.is_featured = payload.is_featured
        if payload.metadata is not None:
            topic.metadata_json = payload.metadata
        if payload.extra is not None:
            topic.extra_json = payload.extra
        if payload.group_slug or payload.group_name or payload.group:
            group_name = payload.group_name or payload.group
            group_slug = payload.group_slug or (slugify(group_name) if group_name else None)
            group = await self.get_or_create_group(group_slug, group_name)
            topic.group_id = group.id if group else None
        if payload.domain_slug or payload.domain_name or payload.domain:
            domain_name = payload.domain_name or payload.domain
            domain_slug = payload.domain_slug or (slugify(domain_name) if domain_name else None)
            domain = await self.get_or_create_domain(domain_slug, domain_name)
            topic.domain_id = domain.id if domain else None
        parent_slug = payload.parent_topic_slug or payload.parent_topic_id
        if parent_slug is not None:
            parent = await self.session.scalar(select(Topic).where(Topic.slug == parent_slug))
            topic.parent_topic_id = parent.id if parent else None

        next_body = payload.resolved_body_markdown
        body_changed = next_body is not None and next_body != topic.body_markdown
        if body_changed:
            topic.body_markdown = next_body or ""
            topic.body_plain_text = markdown_to_plain_text(topic.body_markdown)
            topic.body_hash = sha256_text(topic.body_markdown)
            topic.word_count = word_count(topic.body_plain_text)
            topic.reading_time_minutes = reading_minutes(topic.word_count)
            topic.version += 1

        if payload.sections is not None or body_changed:
            await self._replace_sections(topic, payload.sections)
        if payload.tags is not None:
            await self._replace_tags(topic, payload.tags)
        if payload.resolved_source_keys is not None:
            await self._replace_sources(topic, payload.resolved_source_keys)

        if body_changed:
            self.session.add(
                TopicRevision(
                    topic_id=topic.id,
                    version=topic.version,
                    title=topic.title,
                    summary=topic.summary,
                    body_markdown=topic.body_markdown,
                    body_hash=topic.body_hash,
                    change_note=payload.change_note,
                    actor=actor,
                )
            )

        await self.session.flush()
        return await self.get_topic_detail(topic.slug, status=None)

    async def soft_delete_topic(self, slug: str) -> bool:
        result = await self.session.execute(
            update(Topic)
            .where(Topic.slug == slug, Topic.deleted_at.is_(None))
            .values(deleted_at=func.now(), status=TopicStatus.archived)
        )
        await self.session.flush()
        return bool(result.rowcount)

    async def reindex_search(self) -> None:
        await self.session.execute(text("select refresh_topic_search_vectors()"))
        await self.session.flush()
