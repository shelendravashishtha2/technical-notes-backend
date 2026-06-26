from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, bool]:
    return {"ok": True}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    result = await session.execute(text("select now() as now"))
    return {"ok": True, "database_time": result.scalar_one().isoformat()}
