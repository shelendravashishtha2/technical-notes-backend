from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.topics import TopicRepository
from app.schemas.exports import (
    ExportHydrateResponse,
    ExportManifestResponse,
    ExportManifestTopic,
    ExportSelection,
)
from app.utils.http import set_cache_headers
from app.utils.text import sha256_text

router = APIRouter(prefix="/exports", tags=["exports"])


def _selection_hash(selection: ExportSelection) -> str:
    return sha256_text(selection.model_dump_json())


def _ensure_selection(selection: ExportSelection) -> list[str]:
    ids = selection.resolved_topic_ids
    if not ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one topic.")
    return ids


@router.post("/manifest", response_model=ExportManifestResponse)
async def export_manifest(
    selection: ExportSelection,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ExportManifestResponse:
    repo = TopicRepository(session)
    topic_ids = _ensure_selection(selection)
    topics = await repo.batch_get_topics(
        topic_ids,
        include_sections=True,
        include_sources=False,
        include_assets=False,
        include_section_bodies=False,
    )
    manifest_topics = [ExportManifestTopic(topic=topic, sections=topic.sections) for topic in topics]
    payload = ExportManifestResponse(
        selection_hash=_selection_hash(selection),
        topic_count=len(topics),
        section_count=sum(topic.section_count for topic in topics),
        total_word_count=sum(topic.word_count for topic in topics),
        estimated_reading_minutes=sum(topic.reading_time_minutes for topic in topics),
        topics=manifest_topics,
    )
    set_cache_headers(response, etag=f'W/"{payload.selection_hash}"', seconds=300)
    return payload


@router.post("/hydrate", response_model=ExportHydrateResponse)
async def export_hydrate(
    selection: ExportSelection,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ExportHydrateResponse:
    repo = TopicRepository(session)
    topic_ids = _ensure_selection(selection)
    topics = await repo.batch_get_topics(
        topic_ids,
        include_sections=True,
        include_sources=selection.include_sources,
        include_assets=selection.include_assets,
        include_section_bodies=True,
    )
    payload = ExportHydrateResponse(
        selection_hash=_selection_hash(selection),
        topics=topics,
        metadata={
            "topic_count": len(topics),
            "total_word_count": sum(topic.word_count for topic in topics),
            "section_ids": selection.section_ids,
            "scope": selection.scope,
        },
    )
    set_cache_headers(response, etag=f'W/"{payload.selection_hash}"', seconds=120)
    return payload
