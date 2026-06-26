from __future__ import annotations

from typing import Annotated
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.config import settings
from app.db.session import get_session
from app.models.content import TopicStatus
from app.repositories.bootstrap import BootstrapRepository
from app.repositories.topics import TopicRepository
from app.schemas.pagination import CursorPage
from app.schemas.topics import GroupedTopicTree, TopicBatchRequest, TopicDetail, TopicListItem
from app.utils.http import content_etag, not_modified_if_match, set_cache_headers, weak_etag_for

router = APIRouter(prefix="/topics", tags=["topics"])




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

def _topic_headers(etag: str, *, seconds: int | None = None) -> dict[str, str]:
    ttl = seconds if seconds is not None else settings.topic_cache_seconds
    return {
        "Cache-Control": f"public, max-age={ttl}, stale-while-revalidate={ttl * 2}",
        "ETag": etag,
    }


@router.get("", response_model=CursorPage[TopicListItem])
async def list_topics(
    response: Response,
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str | None = None,
    group: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    featured: bool | None = None,
    include_sections: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[TopicListItem]:
    page = await TopicRepository(session).list_topics(
        limit=limit,
        cursor=cursor,
        group=group,
        domain=domain,
        tag=tag,
        featured=featured,
        include_sections=include_sections,
    )
    set_cache_headers(response, etag=weak_etag_for(page.model_dump(mode="json")), seconds=120)
    return page


@router.get("/tree", response_model=list[GroupedTopicTree])
async def topic_tree(response: Response, session: AsyncSession = Depends(get_session)) -> list[GroupedTopicTree]:
    cache_key = "topics:tree:v2"
    cached = await cache.get(cache_key)
    if cached is not None:
        set_cache_headers(response, etag=weak_etag_for(cached), seconds=settings.nav_cache_seconds)
        return cached
    tree = await TopicRepository(session).list_grouped_tree()
    payload = [GroupedTopicTree(**item).model_dump(mode="json") for item in tree]
    await cache.set(cache_key, payload, settings.nav_cache_seconds)
    set_cache_headers(response, etag=weak_etag_for(payload), seconds=settings.nav_cache_seconds)
    return payload


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
    include_sources: bool = Query(default=True),
    include_assets: bool = Query(default=False),  # Kept for API compatibility; fast path omits assets.
    include_section_bodies: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
):
    cache_key = _topic_cache_key(
        topic_id,
        include_sources=include_sources,
        include_assets=include_assets,
        include_section_bodies=include_section_bodies,
    )

    cached = await cache.get(cache_key)
    if cached is not None:
        payload = cached["payload"] if isinstance(cached, dict) and "payload" in cached else cached
        etag = cached.get("etag") if isinstance(cached, dict) else content_etag(
            payload.get("id"), payload.get("body_hash"), payload.get("version")
        )
        maybe = not_modified_if_match(if_none_match, etag)
        if maybe:
            return maybe
        return ORJSONResponse(payload, headers=_topic_headers(etag))

    # Persistent cache: survives app restart and avoids the expensive first
    # Neon/SQL payload build. This is intentionally checked after memory cache
    # and before DB hydration.
    persistent = await BootstrapRepository(session).get_cached(cache_key)
    if persistent is not None:
        payload, etag = persistent
        await cache.set(cache_key, {"payload": payload, "etag": etag}, settings.topic_cache_seconds)
        maybe = not_modified_if_match(if_none_match, etag)
        if maybe:
            return maybe
        return ORJSONResponse(payload, headers=_topic_headers(etag))

    payload = await TopicRepository(session).get_topic_detail_payload_fast(
        topic_id,
        include_sections=True,
        include_sources=include_sources,
        include_section_bodies=include_section_bodies,
    )
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    etag = content_etag(payload["id"], payload["body_hash"], payload["version"])
    maybe = not_modified_if_match(if_none_match, etag)
    if maybe:
        return maybe

    await cache.set(cache_key, {"payload": payload, "etag": etag}, settings.topic_cache_seconds)
    await BootstrapRepository(session).set_cached(payload, etag, cache_key)
    await session.commit()
    return ORJSONResponse(payload, headers=_topic_headers(etag))


@router.get("/{topic_id}/sections")
async def topic_sections(
    topic_id: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    payload = await TopicRepository(session).get_topic_detail_payload_fast(
        topic_id,
        include_sections=True,
        include_sources=False,
        include_section_bodies=False,
    )
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    sections = payload["sections"]
    set_cache_headers(response, etag=weak_etag_for(sections), seconds=settings.topic_cache_seconds)
    return ORJSONResponse(sections)


@router.post("/batch")
async def batch_topics(
    payload: TopicBatchRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    if not payload.topic_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide ids or slugs.")
    repo = TopicRepository(session)
    items = []
    for slug in payload.topic_ids:
        topic = await repo.get_topic_detail_payload_fast(
            slug,
            include_sections=payload.include_sections,
            include_sources=payload.include_sources,
            include_section_bodies=payload.include_section_bodies,
        )
        if topic:
            items.append(topic)
    set_cache_headers(response, etag=weak_etag_for(items), seconds=120)
    return ORJSONResponse(items)


@router.post("/hydrate")
async def hydrate_topics(
    payload: TopicBatchRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Alias for the current React lazy/full-scroll/export hydration flow."""
    return await batch_topics(payload, response, session)
