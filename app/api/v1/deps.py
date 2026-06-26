from __future__ import annotations

from typing import Annotated

from fastapi import Query

from app.core.config import settings


def page_limit(limit: Annotated[int | None, Query(ge=1)] = None) -> int:
    value = limit or settings.default_page_size
    return min(value, settings.max_page_size)
