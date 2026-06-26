from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    kind: Literal["topic", "section"]
    topicId: str
    topicTitle: str
    sectionId: str | None = None
    sectionTitle: str | None = None
    sectionPath: list[str] = Field(default_factory=list)
    group: str | None = None
    domain: str | None = None
    rank: float
    snippet: str
    bodyHash: str

    # Backend-friendly aliases kept for admin/debug clients.
    topic_slug: str
    section_slug: str | None = None


class SearchSuggestResult(BaseModel):
    label: str
    value: str
    kind: Literal["topic", "tag", "group", "domain"]
