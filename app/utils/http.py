from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

import orjson
from fastapi import Response, status


def json_dumps(value: Any) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS | orjson.OPT_SERIALIZE_UUID)


def weak_etag_for(value: Any) -> str:
    payload = json_dumps(value)
    return f'W/"{hashlib.sha256(payload).hexdigest()}"'


def content_etag(*parts: str | int | None) -> str:
    source = ":".join(str(part or "") for part in parts)
    return f'W/"{hashlib.sha256(source.encode("utf-8")).hexdigest()}"'


def not_modified_if_match(if_none_match: str | None, etag: str) -> Response | None:
    if if_none_match and hmac.compare_digest(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return None


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def set_cache_headers(response: Response, *, etag: str | None = None, seconds: int = 60) -> None:
    response.headers["Cache-Control"] = f"private, max-age={seconds}, stale-while-revalidate={seconds * 2}"
    if etag:
        response.headers["ETag"] = etag
