from __future__ import annotations

import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.security import require_admin
from app.db.session import get_session
from app.models.content import AuditLog
from app.repositories.bootstrap import BootstrapRepository
from app.repositories.topics import TopicRepository
from app.schemas.common import APIMessage
from app.schemas.topics import TopicBulkUpsertRequest, TopicCreate, TopicDetail, TopicUpdate

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])




def _topic_cache_key(
    topic_id: str,
    *,
    include_sources: bool,
    include_assets: bool,
    include_section_bodies: bool,
) -> str:
    raw = (
        f"{topic_id}|sources={int(include_sources)}|"
        f"assets={int(include_assets)}|sectionBodies={int(include_section_bodies)}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"topics:detail:v6:{digest}"

async def _audit(
    session: AsyncSession,
    request: Request,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    after: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor=getattr(request.state, "actor", "admin"),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
            after_json=after,
        )
    )


async def _clear_content_caches(session: AsyncSession | None = None) -> None:
    await cache.delete_prefix("topics:")
    await cache.delete_prefix("bootstrap:")
    if session is not None:
        repo = BootstrapRepository(session)
        await repo.invalidate("bootstrap:")
        await repo.invalidate("topics:")


@router.post("/topics", response_model=TopicDetail, status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TopicDetail:
    repo = TopicRepository(session)
    topic = await repo.create_topic(payload, actor="admin")
    await _audit(
        session,
        request,
        action="create",
        entity_type="topic",
        entity_id=topic.id,
        after=topic.model_dump(mode="json"),
    )
    await _clear_content_caches(session)
    await session.commit()
    return topic


@router.patch("/topics/{topic_id}", response_model=TopicDetail)
async def update_topic(
    topic_id: str,
    payload: TopicUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TopicDetail:
    repo = TopicRepository(session)
    topic = await repo.update_topic(topic_id, payload, actor="admin")
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    await _audit(
        session,
        request,
        action="update",
        entity_type="topic",
        entity_id=topic.id,
        after=topic.model_dump(mode="json"),
    )
    await _clear_content_caches(session)
    await session.commit()
    return topic


@router.delete("/topics/{topic_id}", response_model=APIMessage)
async def delete_topic(
    topic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> APIMessage:
    repo = TopicRepository(session)
    deleted = await repo.soft_delete_topic(topic_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    await _audit(session, request, action="soft_delete", entity_type="topic", entity_id=topic_id)
    await _clear_content_caches(session)
    await session.commit()
    return APIMessage(message="Topic archived")


@router.post("/topics/bulk-upsert", response_model=list[TopicDetail])
async def bulk_upsert_topics(
    payload: TopicBulkUpsertRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[TopicDetail]:
    """Compatibility endpoint that returns hydrated topics.

    For large imports, prefer /topics/bulk-upsert-fast because returning all
    full topic details makes imports slow and memory-heavy.
    """
    repo = TopicRepository(session)
    output: list[TopicDetail] = []
    for item in payload.topics:
        topic_id = item.resolved_slug
        existing = await repo.get_topic_detail(topic_id, status=None) if topic_id else None
        if existing and payload.mode == "insert_only":
            continue
        if not existing and payload.mode == "update_only":
            continue
        if existing:
            update_payload = TopicUpdate(
                **item.model_dump(exclude={"resolved_slug", "resolved_body_markdown", "resolved_source_keys"})
            )
            topic = await repo.update_topic(topic_id, update_payload, actor="admin")
        else:
            topic = await repo.create_topic(item, actor="admin")
        if topic:
            output.append(topic)
    await _audit(session, request, action="bulk_upsert", entity_type="topic", after={"count": len(output)})
    await _clear_content_caches(session)
    await session.commit()
    return output


@router.post("/topics/bulk-upsert-fast")
async def bulk_upsert_topics_fast(
    payload: TopicBulkUpsertRequest,
    request: Request,
    rebuild_bootstrap: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
):
    """Bulk import endpoint optimized for large note sets.

    It does not return hydrated topics. It upserts records, commits once, and
    optionally rebuilds the persistent bootstrap cache once.
    """
    repo = TopicRepository(session)
    created = 0
    updated = 0
    skipped = 0
    slugs: list[str] = []

    for item in payload.topics:
        result = await repo.upsert_topic_slim(item, mode=payload.mode, actor="admin")
        if result["action"] == "created":
            created += 1
            slugs.append(result["slug"])
        elif result["action"] == "updated":
            updated += 1
            slugs.append(result["slug"])
        else:
            skipped += 1

    await _audit(
        session,
        request,
        action="bulk_upsert_fast",
        entity_type="topic",
        after={"created": created, "updated": updated, "skipped": skipped},
    )
    await _clear_content_caches(session)
    await session.commit()

    bootstrap_refreshed = False
    if rebuild_bootstrap:
        await BootstrapRepository(session).refresh()
        await session.commit()
        bootstrap_refreshed = True

    return ORJSONResponse(
        {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "count": created + updated,
            "bootstrap_refreshed": bootstrap_refreshed,
            "slugs": slugs[:100],
        }
    )


@router.post("/search/reindex", response_model=APIMessage)
async def reindex_search(session: AsyncSession = Depends(get_session)) -> APIMessage:
    await TopicRepository(session).reindex_search()
    await _clear_content_caches(session)
    await session.commit()
    return APIMessage(message="Search vectors refreshed")


@router.post("/cache/bootstrap/rebuild")
async def rebuild_bootstrap_cache(session: AsyncSession = Depends(get_session)):
    payload, etag = await BootstrapRepository(session).refresh()
    await session.commit()
    await cache.delete_prefix("bootstrap:")
    return ORJSONResponse(
        {"message": "Bootstrap cache rebuilt", "etag": etag, "topic_count": len(payload.get("topics", []))}
    )




@router.post("/cache/topics/rebuild")
async def rebuild_topic_detail_cache(
    include_sources: bool = Query(default=True),
    include_section_bodies: bool = Query(default=True),
    limit: int = Query(default=5000, ge=1, le=5000),
    session: AsyncSession = Depends(get_session),
):
    """Prebuild topic-detail caches so the first user never pays the DB build cost.

    Recommended after bulk imports/deploys. It writes one app_cache row per topic
    and also warms the current process memory cache.
    """
    started = time.perf_counter()
    bootstrap_repo = BootstrapRepository(session)
    topic_repo = TopicRepository(session)

    await bootstrap_repo.invalidate("topics:")
    await cache.delete_prefix("topics:")

    topics = await bootstrap_repo.topics_fast(include_source_files=False)
    warmed = 0
    total_bytes = 0
    failures: list[dict[str, str]] = []

    for item in topics[:limit]:
        slug = item["id"]
        cache_key = _topic_cache_key(
            slug,
            include_sources=include_sources,
            include_assets=False,
            include_section_bodies=include_section_bodies,
        )
        try:
            payload = await topic_repo.get_topic_detail_payload_fast(
                slug,
                include_sections=True,
                include_sources=include_sources,
                include_section_bodies=include_section_bodies,
            )
            if not payload:
                continue
            from app.utils.http import content_etag
            etag = content_etag(payload["id"], payload["body_hash"], payload["version"])
            await bootstrap_repo.set_cached(payload, etag, cache_key)
            await cache.set(cache_key, {"payload": payload, "etag": etag}, settings.topic_cache_seconds)
            # Quick approximate payload size without storing the bytes.
            total_bytes += len(payload.get("content") or "")
            warmed += 1
        except Exception as exc:  # keep warming the remaining topics
            await session.rollback()
            failures.append({"slug": slug, "error": str(exc)[:300]})

    await session.commit()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return ORJSONResponse(
        {
            "message": "Topic detail cache rebuilt",
            "warmed": warmed,
            "failed": len(failures),
            "failures": failures[:10],
            "approx_content_bytes": total_bytes,
            "elapsed_ms": elapsed_ms,
            "include_sources": include_sources,
            "include_section_bodies": include_section_bodies,
        }
    )


@router.delete("/cache/bootstrap")
async def clear_bootstrap_cache(session: AsyncSession = Depends(get_session)):
    await cache.delete_prefix("bootstrap:")
    await BootstrapRepository(session).invalidate("bootstrap:")
    await session.commit()
    return ORJSONResponse({"message": "Bootstrap cache cleared"})
