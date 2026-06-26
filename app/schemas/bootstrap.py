from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.taxonomy import TaxonomyItem
from app.schemas.topics import GroupedTopicTree, TopicListItem


class BootstrapStats(BaseModel):
    topic_count: int
    section_count: int
    tag_count: int
    content_version: str


class BootstrapResponse(BaseModel):
    stats: BootstrapStats
    groupOrderPreference: list[str] = Field(default_factory=list)
    groups: list[TaxonomyItem] = Field(default_factory=list)
    domains: list[TaxonomyItem] = Field(default_factory=list)
    tags: list[TaxonomyItem] = Field(default_factory=list)
    topics: list[TopicListItem] = Field(default_factory=list)
    tree: list[GroupedTopicTree] = Field(default_factory=list)
