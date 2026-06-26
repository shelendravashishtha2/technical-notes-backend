# Architecture

```txt
React frontend
  ↓
FastAPI API on Render
  ↓
Neon Postgres
```

## Request strategy

The app should avoid downloading all markdown on startup.

```txt
Startup:       GET /bootstrap
Open topic:    GET /topics/{id}
Full scroll:   POST /topics/hydrate
PDF export:    POST /exports/hydrate
Search:        GET /search
```

## Storage strategy

- `topics` keeps metadata and full markdown.
- `topic_sections` keeps searchable/jumpable section records.
- `groups` and `domains` keep navigation/filter ordering.
- `source_files` maps directly to frontend `sourceFiles`.
- `topic_revisions` keeps safe edit history.
- `saved_selections` and `note_collections` support future reader/export flows.

## Caching strategy

- Bootstrap and tree endpoints are cacheable with ETags.
- Topic detail uses content hash + version for ETags.
- Batch hydrate is short-cacheable.
- Redis is optional. Without Redis, the app uses in-process cache.

## Security strategy

- Frontend never connects to Neon directly.
- Admin writes require a secret token.
- CORS is explicit.
- Trusted hosts are explicit.
- Basic rate limiting is included.
- Public endpoints only return published, non-deleted topics.
