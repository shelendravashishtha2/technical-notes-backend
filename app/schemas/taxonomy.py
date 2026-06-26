from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaxonomyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    description: str | None = None
    sort_order: int = 0
    topic_count: int | None = None
