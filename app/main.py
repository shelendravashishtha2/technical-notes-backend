from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.api.v1.router import api_router
from app.core.cache import cache
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware, SimpleRateLimitMiddleware
from app.schemas.common import ProblemDetail

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.close()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SimpleRateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)

if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "X-Request-ID", "If-None-Match"],
    expose_headers=["ETag", "X-Request-ID"],
    max_age=86400,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    problem = ProblemDetail(
        title="Request validation failed",
        status=HTTP_422_UNPROCESSABLE_ENTITY,
        detail="One or more request fields are invalid.",
        instance=str(request.url.path),
        request_id=request_id,
        meta={"errors": exc.errors()},
    )
    return ORJSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=problem.model_dump())


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "health": f"{settings.api_v1_prefix}/health/live"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
