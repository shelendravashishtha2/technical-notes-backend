from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

from app.schemas.topics import TopicDetail, TopicListItem, TopicSectionOut


class ExportSelection(BaseModel):
    topic_ids: list[str] = Field(default_factory=list, max_length=200)
    topic_slugs: list[str] = Field(default_factory=list, max_length=200)
    section_ids: list[str] = Field(default_factory=list, max_length=1000)
    include_children: bool = True
    include_sources: bool = True
    include_assets: bool = False
    scope: Literal["topics", "sections", "all"] = "topics"

    @computed_field  # type: ignore[misc]
    @property
    def resolved_topic_ids(self) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for raw in [*self.topic_ids, *self.topic_slugs]:
            key = raw.strip()
            if key and key not in seen:
                seen.add(key)
                output.append(key)
        return output


class ExportManifestTopic(BaseModel):
    topic: TopicListItem
    sections: list[TopicSectionOut] = Field(default_factory=list)


class ExportManifestResponse(BaseModel):
    selection_hash: str
    topic_count: int
    section_count: int
    total_word_count: int
    estimated_reading_minutes: int
    topics: list[ExportManifestTopic]


class ExportHydrateResponse(BaseModel):
    selection_hash: str
    topics: list[TopicDetail]
    metadata: dict[str, Any] = Field(default_factory=dict)
