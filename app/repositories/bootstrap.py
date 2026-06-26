from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.http import weak_etag_for


BOOTSTRAP_CACHE_KEY = "bootstrap:v6:compact"


class BootstrapRepository:
    """Fast, non-ORM bootstrap/cache repository.

    Bootstrap is the hottest endpoint in the app. It must not hydrate ORM
    relationships or validate thousands of nested Pydantic objects. This
    repository uses compact SQL projections and an optional persistent
    app_cache row so the normal request path is a single row lookup.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cached(self, cache_key: str = BOOTSTRAP_CACHE_KEY) -> tuple[dict[str, Any], str] | None:
        stmt = text("""
            SELECT payload, etag
            FROM app_cache
            WHERE cache_key = :cache_key
        """)
        try:
            row = (await self.session.execute(stmt, {"cache_key": cache_key})).mappings().one_or_none()
        except Exception:
            # The app_cache table may not exist until migration 0002 is applied.
            # PostgreSQL marks the transaction as failed after an error, so rollback
            # before letting callers continue with fallback queries.
            await self.session.rollback()
            return None
        if not row:
            return None
        return dict(row["payload"]), str(row["etag"])

    async def set_cached(self, payload: dict[str, Any], etag: str, cache_key: str = BOOTSTRAP_CACHE_KEY) -> None:
        stmt = text("""
            INSERT INTO app_cache (cache_key, payload, etag, updated_at)
            VALUES (:cache_key, CAST(:payload AS jsonb), :etag, now())
            ON CONFLICT (cache_key)
            DO UPDATE SET payload = excluded.payload, etag = excluded.etag, updated_at = now()
        """)
        import orjson

        try:
            await self.session.execute(
                stmt,
                {
                    "cache_key": cache_key,
                    "payload": orjson.dumps(payload).decode("utf-8"),
                    "etag": etag,
                },
            )
        except Exception:
            # Keep API functional even before app_cache migration is applied.
            await self.session.rollback()
            return

    async def invalidate(self, prefix: str = "bootstrap:") -> None:
        try:
            await self.session.execute(text("DELETE FROM app_cache WHERE cache_key LIKE :prefix"), {"prefix": f"{prefix}%"})
        except Exception:
            await self.session.rollback()
            return

    async def refresh(self, cache_key: str = BOOTSTRAP_CACHE_KEY) -> tuple[dict[str, Any], str]:
        payload = await self.build_payload()
        etag = weak_etag_for(payload)
        await self.set_cached(payload, etag, cache_key)
        return payload, etag

    async def build_payload(self) -> dict[str, Any]:
        started = time.perf_counter()
        stats = await self.stats_fast()
        after_stats = time.perf_counter()
        groups = await self.groups_fast()
        after_groups = time.perf_counter()
        domains = await self.domains_fast()
        after_domains = time.perf_counter()
        topics = await self.topics_fast(include_source_files=False)
        after_topics = time.perf_counter()

        payload = {
            "stats": stats,
            "groupOrderPreference": stats.get("group_order_preference") or [],
            "groups": groups,
            "domains": domains,
            "tags": [],
            "topics": topics,
            "tree": [],
            "_perf": {
                "stats_ms": round((after_stats - started) * 1000, 2),
                "groups_ms": round((after_groups - after_stats) * 1000, 2),
                "domains_ms": round((after_domains - after_groups) * 1000, 2),
                "topics_ms": round((after_topics - after_domains) * 1000, 2),
                "total_build_ms": round((after_topics - started) * 1000, 2),
            },
        }
        # Remove this before returning to frontend; useful only during debugging.
        payload.pop("_perf", None)
        return payload

    async def stats_fast(self) -> dict[str, Any]:
        stmt = text("""
            SELECT
                (SELECT count(*) FROM topics WHERE status = 'published' AND deleted_at IS NULL)::int AS topic_count,
                (SELECT count(*) FROM topic_sections WHERE deleted_at IS NULL)::int AS section_count,
                (SELECT count(*) FROM tags)::int AS tag_count,
                (SELECT max(updated_at) FROM topics WHERE status = 'published' AND deleted_at IS NULL) AS content_version,
                (SELECT COALESCE(jsonb_agg(name ORDER BY sort_order, name), '[]'::jsonb) FROM groups) AS group_order_preference
        """)
        row = (await self.session.execute(stmt)).mappings().one()
        content_version = row["content_version"]
        return {
            "topic_count": int(row["topic_count"] or 0),
            "section_count": int(row["section_count"] or 0),
            "tag_count": int(row["tag_count"] or 0),
            "content_version": content_version.isoformat() if content_version else "empty",
            "group_order_preference": list(row["group_order_preference"] or []),
        }

    async def groups_fast(self) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT
                g.id::text AS id,
                g.slug,
                g.name,
                g.description,
                g.sort_order,
                count(t.id)::int AS topic_count
            FROM groups g
            LEFT JOIN topics t
              ON t.group_id = g.id
             AND t.status = 'published'
             AND t.deleted_at IS NULL
            GROUP BY g.id, g.slug, g.name, g.description, g.sort_order
            ORDER BY g.sort_order ASC, g.name ASC
        """)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(row) for row in rows]

    async def domains_fast(self) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT
                d.id::text AS id,
                d.slug,
                d.name,
                d.description,
                d.sort_order,
                count(t.id)::int AS topic_count
            FROM domains d
            LEFT JOIN topics t
              ON t.domain_id = d.id
             AND t.status = 'published'
             AND t.deleted_at IS NULL
            GROUP BY d.id, d.slug, d.name, d.description, d.sort_order
            ORDER BY d.sort_order ASC, d.name ASC
        """)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(row) for row in rows]

    async def topics_fast(self, *, include_source_files: bool = False) -> list[dict[str, Any]]:
        source_sql = """
            COALESCE(src.source_files, '[]'::jsonb) AS source_files,
        """ if include_source_files else "'[]'::jsonb AS source_files,"
        source_join = """
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(sf.source_key ORDER BY tsl.relevance, sf.source_key) AS source_files
                FROM topic_source_links tsl
                JOIN source_files sf ON sf.id = tsl.source_id
                WHERE tsl.topic_id = t.id
            ) src ON true
        """ if include_source_files else ""

        stmt = text(f"""
            SELECT
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
                t.order_index,
                t.section_count,
                t.word_count,
                t.reading_time_minutes,
                t.body_hash,
                t.version,
                t.is_featured,
                t.updated_at,
                {source_sql}
                t.extra_json ->> 'contentUrl' AS "contentUrl",
                t.extra_json ->> 'content_url' AS content_url,
                t.extra_json ->> 'contentStorage' AS "contentStorage",
                t.extra_json ->> 'content_storage' AS content_storage
            FROM topics t
            LEFT JOIN groups g ON g.id = t.group_id
            LEFT JOIN domains d ON d.id = t.domain_id
            {source_join}
            WHERE t.deleted_at IS NULL
              AND t.status = 'published'
            ORDER BY t.order_index ASC, t.slug ASC
            LIMIT 5000
        """)
        rows = (await self.session.execute(stmt)).mappings().all()
        output: list[dict[str, Any]] = []
        for row in rows:
            updated_at = row["updated_at"]
            content_url = row.get("contentUrl") or row.get("content_url")
            content_storage = row.get("contentStorage") or row.get("content_storage") or "database"
            item = {
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "summary": row["summary"],
                "group": row["group"],
                "group_slug": row["group_slug"],
                "domain": row["domain"],
                "domain_slug": row["domain_slug"],
                "order_index": row["order_index"],
                "section_count": row["section_count"],
                "word_count": row["word_count"],
                "reading_time_minutes": row["reading_time_minutes"],
                "body_hash": row["body_hash"],
                "content_hash": row["body_hash"],
                "version": row["version"],
                "updated_at": updated_at.isoformat().replace("+00:00", "Z") if updated_at else None,
                "contentStorage": content_storage,
                "contentUrl": content_url,
            }
            # Keep legacy keys only when populated; this keeps bootstrap small.
            if row["subtitle"]:
                item["subtitle"] = row["subtitle"]
            if row["difficulty"]:
                item["difficulty"] = row["difficulty"]
            if row["is_featured"]:
                item["is_featured"] = row["is_featured"]
            if include_source_files:
                item["sourceFiles"] = list(row["source_files"] or [])
            output.append(item)
        return output
