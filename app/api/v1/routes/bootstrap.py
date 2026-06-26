from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.config import settings
from app.db.session import get_session
from app.repositories.bootstrap import BOOTSTRAP_CACHE_KEY, BootstrapRepository
from app.utils.http import not_modified_if_match, weak_etag_for

router = APIRouter(tags=["bootstrap"])


def _headers(etag: str, *, seconds: int | None = None) -> dict[str, str]:
    ttl = seconds if seconds is not None else settings.nav_cache_seconds
    return {
        "Cache-Control": f"public, max-age={ttl}, stale-while-revalidate={ttl * 2}",
        "ETag": etag,
    }


@router.get("/bootstrap")
async def bootstrap(
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
    refresh: bool = Query(default=False, description="Force rebuild of bootstrap cache."),
    session: AsyncSession = Depends(get_session),
):
    """Return the compact startup index.

    This endpoint is intentionally not response_model validated. It is a hot path
    returning a stable prebuilt JSON document. Full markdown, section bodies,
    source details, and export data are loaded lazily from topic endpoints.
    """
    repo = BootstrapRepository(session)

    if not refresh:
        memory = await cache.get(BOOTSTRAP_CACHE_KEY)
        if memory is not None:
            payload = memory["payload"] if isinstance(memory, dict) and "payload" in memory else memory
            etag = memory.get("etag") if isinstance(memory, dict) else weak_etag_for(payload)
            maybe = not_modified_if_match(if_none_match, etag)
            if maybe:
                return maybe
            return ORJSONResponse(payload, headers=_headers(etag))

        cached = await repo.get_cached()
        if cached is not None:
            payload, etag = cached
            await cache.set(BOOTSTRAP_CACHE_KEY, {"payload": payload, "etag": etag}, settings.nav_cache_seconds)
            maybe = not_modified_if_match(if_none_match, etag)
            if maybe:
                return maybe
            return ORJSONResponse(payload, headers=_headers(etag))

    payload, etag = await repo.refresh()
    await session.commit()
    await cache.set(BOOTSTRAP_CACHE_KEY, {"payload": payload, "etag": etag}, settings.nav_cache_seconds)
    maybe = not_modified_if_match(if_none_match, etag)
    if maybe:
        return maybe
    return ORJSONResponse(payload, headers=_headers(etag))
