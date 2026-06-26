from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.repositories.taxonomy import TaxonomyRepository
from app.schemas.taxonomy import TaxonomyItem
from app.utils.http import set_cache_headers, weak_etag_for

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("/groups", response_model=list[TaxonomyItem])
async def groups(response: Response, session: AsyncSession = Depends(get_session)) -> list[TaxonomyItem]:
    items = await TaxonomyRepository(session).list_groups()
    set_cache_headers(response, etag=weak_etag_for([item.model_dump(mode="json") for item in items]), seconds=settings.nav_cache_seconds)
    return items


@router.get("/domains", response_model=list[TaxonomyItem])
async def domains(response: Response, session: AsyncSession = Depends(get_session)) -> list[TaxonomyItem]:
    items = await TaxonomyRepository(session).list_domains()
    set_cache_headers(response, etag=weak_etag_for([item.model_dump(mode="json") for item in items]), seconds=settings.nav_cache_seconds)
    return items


@router.get("/tags", response_model=list[TaxonomyItem])
async def tags(response: Response, session: AsyncSession = Depends(get_session)) -> list[TaxonomyItem]:
    items = await TaxonomyRepository(session).list_tags()
    set_cache_headers(response, etag=weak_etag_for([item.model_dump(mode="json") for item in items]), seconds=settings.nav_cache_seconds)
    return items
