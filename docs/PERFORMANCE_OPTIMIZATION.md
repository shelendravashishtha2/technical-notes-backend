# Performance Optimization Notes

This backend is optimized around one rule:

> `/api/v1/bootstrap` is a startup index, not a live ORM aggregation endpoint.

## What changed

### 1. Compact bootstrap

`GET /api/v1/bootstrap` now returns a compact startup payload:

- stats
- group order
- groups
- domains
- lightweight topic metadata
- no full markdown
- no section arrays
- no duplicated tree
- no source file arrays by default

Full content is fetched lazily from:

```http
GET /api/v1/topics/{topic_id}
```

Batch/full-scroll/export hydration uses:

```http
POST /api/v1/topics/hydrate
```

### 2. Persistent bootstrap cache

A new `app_cache` table stores prebuilt JSON payloads.

Normal bootstrap request path becomes:

```sql
SELECT payload, etag FROM app_cache WHERE cache_key = 'bootstrap:v6:compact';
```

That avoids rebuilding ORM/Pydantic objects on every app load.

### 3. Fast SQL projections

Bootstrap uses raw SQL projections instead of SQLAlchemy relationship hydration. This avoids:

- `selectinload` relationship fan-out
- Pydantic validation of thousands of nested objects
- repeated serialization of empty `sections` / `tags` / `tree`

### 4. Fast import endpoint

Use:

```http
POST /api/v1/admin/topics/bulk-upsert-fast?rebuild_bootstrap=false
```

instead of the compatibility endpoint:

```http
POST /api/v1/admin/topics/bulk-upsert
```

The fast endpoint returns counts only, not every hydrated topic.

At the end of import, rebuild the bootstrap cache once:

```http
POST /api/v1/admin/cache/bootstrap/rebuild
```

The included `scripts/import_curated_notes.mjs` already does this.

## Commands after pulling this version

```bash
uv sync
uv run alembic upgrade head

uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Rebuild bootstrap cache manually:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/admin/cache/bootstrap/rebuild" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

Measure bootstrap:

```bash
curl -s -o /tmp/bootstrap.json \
  -w "time_total=%{time_total}s size=%{size_download} bytes\n" \
  http://127.0.0.1:8000/api/v1/bootstrap
```

Run twice. The second call should normally be extremely fast because it hits in-memory cache.

## Expected target

For 140 topics / 2,855 sections:

- cached local bootstrap: under 100-300 ms
- persistent cache local bootstrap: under 500 ms
- cold rebuild: depends on Neon latency, but should be seconds, not tens of seconds

If cold rebuild is still slow, use the cached path in production and rebuild only after admin imports/updates.
