# Technical Notes API

A production-oriented FastAPI backend for a technical notes reader.

It is designed around one rule:

> startup data should be light, searchable content should stay structured, and full markdown should only be loaded when the reader actually needs it.

This project serves frontend-friendly JSON, stores content in a normalized PostgreSQL schema, and uses layered caching so the common read paths stay fast even as the note library grows.

## What This Project Solves

Many note readers start simple and then hit the same wall:

- the frontend wants a flat, easy-to-render JSON shape
- the database needs a more structured model
- loading every note body on app startup becomes wasteful
- export, search, and section navigation need more than a single markdown blob

This API solves that by separating:

- **navigation payloads** from **reading payloads**
- **storage structure** from **response structure**
- **public read traffic** from **privileged write operations**

## At A Glance

| Concern | Approach in this project |
| --- | --- |
| Fast app startup | `GET /api/v1/bootstrap` returns a compact prebuilt index |
| Read full note content | `GET /api/v1/topics/{topic_id}` hydrates one topic lazily |
| Full-scroll mode and PDF export | Batch hydration endpoints avoid one-request-per-topic behavior |
| Search quality | PostgreSQL full-text search with `TSVECTOR`, `websearch_to_tsquery`, and highlighted snippets |
| Frontend compatibility | Stable note ids such as `aws-s3` are preserved as public `id` values |
| Scalability | Normalized relational schema behind denormalized API payloads |
| Operations | Alembic migrations, health checks, cache rebuild endpoints, Docker and Render support |
| Security | Admin-token-protected writes, explicit CORS/trusted hosts, rate limiting, security headers |

## Core Theory

### 1. Read model and write model should not be the same thing

The frontend wants easy payloads:

- lightweight lists for navigation
- a single fully hydrated topic for reading
- a batch of full topics for export or continuous scroll

The database, however, benefits from normalized tables:

- topics
- sections
- taxonomy
- sources
- revisions
- audit data

This project keeps the database relational and expressive, then projects that data into frontend-friendly JSON at the API boundary.

### 2. Startup should fetch an index, not a library

The hottest endpoint in the app is `GET /api/v1/bootstrap`. It is intentionally treated as a startup index, not a giant ORM serialization step.

That means:

- no full markdown bodies in bootstrap
- no expensive relationship fan-out for every app load
- no rebuilding the same navigation document on every request

Instead, the reader loads:

1. a compact bootstrap payload at startup
2. one topic on demand when the user opens it
3. multiple topics only when the UI needs export or full-scroll hydration

### 3. Sections deserve first-class structure

Sections are stored as rows in `topic_sections`, not just as transient markdown parsing output.

That enables:

- table of contents rendering
- section-level search hits
- export by selected section
- future per-section annotations, progress, or quizzes

### 4. Cache is part of the architecture, not a bolt-on

The project uses multiple cache layers:

1. in-process memory cache or optional Redis
2. persistent JSON payloads in the `app_cache` table
3. fresh SQL projection or ORM fallback only when needed

This is especially important for:

- bootstrap payloads
- topic detail hydration
- repeated frontend loads after deployment or restart

## Architecture

```text
React reader
    |
    |  GET /bootstrap
    |  GET /topics/{id}
    |  POST /topics/hydrate
    |  GET /search
    v
FastAPI application
    |
    |  routes -> repositories -> schemas
    |  middleware -> cache -> auth -> headers
    v
Cache tier
    |
    |  memory cache or Redis
    |  persistent JSON cache in app_cache
    v
Neon Postgres
    |
    |  normalized content tables
    |  full-text search vectors
    |  audit and revision data
```

### Request Strategy

```text
Startup navigation:   GET  /api/v1/bootstrap
Topic list:           GET  /api/v1/topics
Single topic read:    GET  /api/v1/topics/{topic_id}
Section outline:      GET  /api/v1/topics/{topic_id}/sections
Batch hydration:      POST /api/v1/topics/batch
Hydration alias:      POST /api/v1/topics/hydrate
Search:               GET  /api/v1/search
Suggestions:          GET  /api/v1/search/suggest
Export preview:       POST /api/v1/exports/manifest
Export hydrate:       POST /api/v1/exports/hydrate
Admin writes:         /api/v1/admin/*
```

### Layer Responsibilities

| Layer | Responsibility |
| --- | --- |
| `app/api/v1/routes` | HTTP concerns: request parsing, response codes, headers, compatibility endpoints |
| `app/repositories` | Data access and projection logic, including fast SQL for hot paths |
| `app/schemas` | Stable request and response contracts via Pydantic |
| `app/models` | SQLAlchemy table definitions and relational structure |
| `app/core` | Settings, cache implementation, middleware, security, logging |
| `app/db` | Async engine and session lifecycle |
| `app/utils` | Text parsing, hashing, cursor helpers, cache header helpers |

## Repository Structure

```text
.
|-- app/
|   |-- api/
|   |   `-- v1/
|   |       |-- deps.py
|   |       |-- router.py
|   |       `-- routes/
|   |           |-- admin.py
|   |           |-- bootstrap.py
|   |           |-- exports.py
|   |           |-- health.py
|   |           |-- search.py
|   |           |-- taxonomy.py
|   |           `-- topics.py
|   |-- core/
|   |   |-- cache.py
|   |   |-- config.py
|   |   |-- logging.py
|   |   |-- middleware.py
|   |   `-- security.py
|   |-- db/
|   |   |-- base.py
|   |   `-- session.py
|   |-- models/
|   |   |-- base.py
|   |   `-- content.py
|   |-- repositories/
|   |   |-- bootstrap.py
|   |   |-- search.py
|   |   |-- taxonomy.py
|   |   `-- topics.py
|   |-- schemas/
|   |   |-- bootstrap.py
|   |   |-- common.py
|   |   |-- exports.py
|   |   |-- pagination.py
|   |   |-- search.py
|   |   |-- taxonomy.py
|   |   `-- topics.py
|   |-- utils/
|   |   |-- http.py
|   |   `-- text.py
|   `-- main.py
|-- alembic/
|   `-- versions/
|-- docs/
|   |-- API_CONTRACT.md
|   |-- ARCHITECTURE.md
|   |-- FRONTEND_INTEGRATION.md
|   |-- PERFORMANCE_OPTIMIZATION.md
|   `-- SCHEMA_DECISIONS.md
|-- infra/
|   `-- sql/
|-- scripts/
|   |-- create_admin_token.py
|   |-- import_curated_notes.mjs
|   `-- sample_topic.json
|-- tests/
|   `-- test_text_utils.py
|-- Dockerfile
|-- alembic.ini
|-- import_notes_to_neon.py
|-- pyproject.toml
|-- render.yaml
`-- uv.lock
```

## Technology Stack

| Area | Choice |
| --- | --- |
| API framework | FastAPI |
| ASGI server | Uvicorn |
| Production process model | Gunicorn + Uvicorn workers |
| ORM / SQL layer | SQLAlchemy 2.x async |
| Database | Neon Postgres |
| Migrations | Alembic |
| Validation / config | Pydantic v2 + pydantic-settings |
| Search | PostgreSQL full-text search |
| Serialization | `orjson` |
| Cache | In-memory cache or optional Redis, plus persistent `app_cache` rows |
| Tooling | `uv` |
| Tests | `pytest` |

## Data Model Philosophy

### Topic identity

The public `topic_id` is the same stable slug the frontend already uses, for example:

```json
{
  "id": "aws-s3",
  "slug": "aws-s3",
  "uuid": "..."
}
```

The UUID remains the internal primary key. The frontend does not need to reason about database identities.

### Canonical content model

The most important tables are:

| Table | Purpose |
| --- | --- |
| `topics` | Canonical note record: title, summary, markdown body, hashes, counts, ordering, status |
| `topic_sections` | Parsed section rows for outlines, search, and export selection |
| `groups` | Top-level navigation grouping |
| `domains` | Secondary taxonomy / filtering |
| `tags` and `topic_tags` | Flexible categorization and future study paths |
| `source_files` and `topic_source_links` | Source provenance behind frontend `sourceFiles` |
| `assets` and `topic_assets` | Optional rich media attachment model |
| `topic_revisions` | Content change history |
| `audit_logs` | Admin activity logging |
| `search_events` | Search observability |
| `app_cache` | Persistent prebuilt JSON payloads for hot endpoints |

### Why full markdown still lives on `topics`

Reading a topic should be simple. One topic detail request should be able to return the full note body without reconstructing it from many section rows. So the system keeps:

- full markdown on `topics.body_markdown`
- structured sections in `topic_sections`

That gives both simplicity for reads and structure for search/export/navigation.

### How content is derived

When content is created or updated, the repository layer computes and stores:

- plain text
- content hashes
- word counts
- estimated reading time
- parsed section records
- search vectors

That precomputation is part of what keeps read endpoints lean.

## API Surface

Base path: `/api/v1`

### Public read endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /bootstrap` | Compact startup payload: stats, taxonomy, lightweight topics |
| `GET /topics` | Cursor-paginated topic metadata |
| `GET /topics/tree` | Grouped topic tree |
| `GET /topics/{topic_id}` | Full topic hydration |
| `GET /topics/{topic_id}/sections` | Section outline only |
| `POST /topics/batch` | Batch topic hydration |
| `POST /topics/hydrate` | Alias for batch hydration |
| `GET /search` | Full-text search with pagination |
| `GET /search/sections` | Compatibility endpoint returning a flat list |
| `GET /search/suggest` | Lightweight suggestions for topic/tag/group/domain lookup |
| `GET /taxonomy/groups` | Group taxonomy |
| `GET /taxonomy/domains` | Domain taxonomy |
| `GET /taxonomy/tags` | Tag taxonomy |
| `POST /exports/manifest` | Export preview and selection summary |
| `POST /exports/hydrate` | Full export hydration |
| `GET /health/live` | Liveness probe |
| `GET /health/ready` | Readiness probe with DB check |

### Admin endpoints

All admin routes require either `X-Admin-Token` or `Authorization: Bearer <token>`.

| Endpoint | Purpose |
| --- | --- |
| `POST /admin/topics` | Create a topic |
| `PATCH /admin/topics/{topic_id}` | Update a topic |
| `DELETE /admin/topics/{topic_id}` | Soft-delete / archive a topic |
| `POST /admin/topics/bulk-upsert` | Compatibility bulk upsert that returns hydrated topics |
| `POST /admin/topics/bulk-upsert-fast` | High-throughput import path |
| `POST /admin/search/reindex` | Refresh search vectors |
| `POST /admin/cache/bootstrap/rebuild` | Rebuild compact bootstrap cache |
| `POST /admin/cache/topics/rebuild` | Warm topic detail caches |
| `DELETE /admin/cache/bootstrap` | Clear bootstrap cache |

## Request and Cache Flow

### Bootstrap flow

```text
Client requests /bootstrap
    -> memory cache or Redis hit, if available
    -> else persistent app_cache row lookup
    -> else compact SQL build
    -> persist payload + ETag
    -> return cacheable JSON
```

The bootstrap repository intentionally avoids full ORM hydration for this endpoint. It uses compact SQL projections because bootstrap is the hottest path in the system.

### Topic detail flow

```text
Client requests /topics/{id}
    -> memory cache or Redis hit, if available
    -> else persistent app_cache row lookup
    -> else fast SQL payload build
    -> persist payload + ETag
    -> return full topic detail
```

The topic detail cache key varies by response options such as:

- `include_sources`
- `include_assets`
- `include_section_bodies`

### Search flow

Search uses PostgreSQL full-text search over topic and section vectors:

- `websearch_to_tsquery` parses user-style search syntax
- `ts_rank_cd` ranks results
- `ts_headline` builds highlighted snippets

This allows section-level hits instead of only topic-level matches.

## Example Payloads

### Bootstrap

```http
GET /api/v1/bootstrap
```

```json
{
  "stats": {
    "topic_count": 140,
    "section_count": 2855,
    "tag_count": 0,
    "content_version": "2026-06-27T00:00:00Z"
  },
  "groupOrderPreference": ["AWS", "Python", "FastAPI"],
  "groups": [],
  "domains": [],
  "tags": [],
  "topics": [],
  "tree": []
}
```

### Single topic hydration

```http
GET /api/v1/topics/aws-s3
```

```json
{
  "id": "aws-s3",
  "title": "S3",
  "group": "AWS",
  "domain": "AWS Storage",
  "summary": "Object storage fundamentals and patterns.",
  "sourceFiles": [],
  "sections": [],
  "content": "# S3\n\n..."
}
```

### Batch hydration

```http
POST /api/v1/topics/hydrate
```

```json
{
  "ids": ["aws-s3", "aws-lambda"],
  "include_sections": true,
  "include_sources": true,
  "include_section_bodies": true
}
```

## Local Development

### Prerequisites

- Python 3.12+
- `uv`
- a PostgreSQL database, typically Neon
- optionally Redis
- Node.js if you want to use the included import script

### Setup

```bash
cp .env.example .env
```

Fill in at least:

- `DATABASE_URL`
- `ALEMBIC_DATABASE_URL` if you do not want it derived automatically
- `ADMIN_TOKEN`

Then install dependencies and migrate:

```bash
uv sync
uv run alembic upgrade head
```

Start the API locally:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Useful URLs in local development:

- API root: `http://localhost:8000/`
- live health: `http://localhost:8000/api/v1/health/live`
- ready health: `http://localhost:8000/api/v1/health/ready`
- docs: `http://localhost:8000/docs`

OpenAPI docs are disabled automatically when `ENVIRONMENT=production`.

## Configuration

The full reference is in `.env.example`. The most important settings are:

| Variable | Meaning |
| --- | --- |
| `APP_NAME` | Service name exposed by the API |
| `ENVIRONMENT` | Environment mode; production hides docs/openapi routes |
| `DEBUG` | Enables SQLAlchemy debug echo and FastAPI debug behavior |
| `DATABASE_URL` | Async runtime database URL |
| `ALEMBIC_DATABASE_URL` | Optional sync URL for Alembic |
| `ADMIN_TOKEN` | Required for all admin routes |
| `CORS_ORIGINS` | Explicit allowed browser origins |
| `TRUSTED_HOSTS` | Explicit host allowlist |
| `JSON_RESPONSE_CACHE_SECONDS` | TTL for smaller cached JSON responses |
| `NAV_CACHE_SECONDS` | TTL for navigation/bootstrap style responses |
| `TOPIC_CACHE_SECONDS` | TTL for topic detail responses |
| `RATE_LIMIT_REQUESTS` | Requests allowed per rate-limit window |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window length |
| `REDIS_URL` | Optional Redis backend for cache storage |

## Common Workflows

### Run tests

```bash
uv run pytest
```

### Run linting

```bash
uv run ruff check .
```

### Import a seed file

The repository includes `scripts/import_curated_notes.mjs` for bulk import through the admin API.

```bash
export API_BASE_URL=http://localhost:8000/api/v1
export ADMIN_TOKEN=your-admin-token

node scripts/import_curated_notes.mjs ./technical-notes-seed.json
```

The importer:

- normalizes incoming topic records
- sends them through `POST /api/v1/admin/topics/bulk-upsert-fast`
- rebuilds bootstrap cache once at the end

### Rebuild bootstrap cache manually

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/admin/cache/bootstrap/rebuild" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

### Warm topic detail caches

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/admin/cache/topics/rebuild" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

## Deployment

### Docker

The included [Dockerfile](Dockerfile):

- installs dependencies with `uv`
- exposes port `10000`
- runs Alembic migrations on container start
- starts Gunicorn with Uvicorn workers

Default container command:

```bash
uv run alembic upgrade head && \
uv run gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT:-10000} \
  --workers ${WEB_CONCURRENCY:-2} \
  --timeout ${WEB_TIMEOUT:-180}
```

### Render

The included [render.yaml](render.yaml) is configured for a Python web service with:

- build command: `pip install uv && uv sync --no-dev`
- start command: `uv run gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 --bind 0.0.0.0:$PORT --timeout 120`
- health check: `/api/v1/health/live`

## Security Posture

The security model is intentionally simple and explicit:

- admin writes require a shared secret token
- public endpoints expose only published, non-deleted content
- CORS is allowlist-based
- trusted hosts are allowlist-based
- request ids are attached to responses
- common security headers are added globally
- a basic IP-and-path rate limiter protects public routes
- the frontend never needs direct database access

## Notes On Performance

Performance is centered on a few practical choices:

- bootstrap uses compact SQL projections instead of deep ORM graph hydration
- topic detail responses are cached with strong identity via hashes and versions
- ETags and `Cache-Control` headers are set across major read endpoints
- gzip compression is enabled for larger responses
- persistent JSON payload caching avoids rebuilding the same documents after restart

For more detail, see [docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md).

## Companion Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md)
- [docs/SCHEMA_DECISIONS.md](docs/SCHEMA_DECISIONS.md)
- [docs/FRONTEND_INTEGRATION.md](docs/FRONTEND_INTEGRATION.md)
- [docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md)

## In One Sentence

This is a FastAPI content backend that treats technical notes like structured, searchable documents rather than static markdown files, while still keeping the frontend payloads simple enough to feel like static data.
