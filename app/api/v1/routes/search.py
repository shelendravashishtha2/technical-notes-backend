from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.repositories.search import SearchRepository
from app.schemas.pagination import OffsetPage, OffsetPageInfo
from app.schemas.search import SearchResult, SearchSuggestResult
from app.utils.http import weak_etag_for, set_cache_headers

router = APIRouter(tags=["search"])


@router.get("/search", response_model=OffsetPage[SearchResult])
async def search(
    response: Response,
    q: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    group: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> OffsetPage[SearchResult]:
    repo = SearchRepository(session)
    results, total = await repo.search(
        query=q,
        limit=limit,
        offset=offset,
        group=group,
        domain=domain,
        tag=tag,
    )
    page = OffsetPage(
        items=results,
        page_info=OffsetPageInfo(
            limit=limit,
            offset=offset,
            returned=len(results),
            total=total,
            has_next_page=offset + len(results) < total,
        ),
    )
    set_cache_headers(response, etag=weak_etag_for(page.model_dump(mode="json")), seconds=settings.json_response_cache_seconds)
    return page


@router.get("/search/sections", response_model=list[SearchResult])
async def search_sections_compat(
    response: Response,
    q: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=18, ge=1, le=50),
    group: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[SearchResult]:
    """Frontend-friendly compatibility endpoint returning the result list directly."""
    results, _ = await SearchRepository(session).search(
        query=q,
        limit=limit,
        offset=0,
        group=group,
        domain=domain,
        tag=tag,
    )
    set_cache_headers(response, etag=weak_etag_for([item.model_dump(mode="json") for item in results]), seconds=settings.json_response_cache_seconds)
    return results


@router.get("/search/suggest", response_model=list[SearchSuggestResult])
async def suggest(
    response: Response,
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> list[SearchSuggestResult]:
    repo = SearchRepository(session)
    results = await repo.suggest(query=q, limit=limit)
    set_cache_headers(response, etag=weak_etag_for([item.model_dump() for item in results]), seconds=120)
    return results
