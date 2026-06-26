from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings


async def require_admin(
    request: Request,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    supplied = x_admin_token
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()

    if not supplied or not hmac.compare_digest(supplied, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token missing or invalid.",
        )
    request.state.actor = "admin"
    return "admin"
