# Schema Decisions

## Why `topics.slug` is the frontend `id`

Your React app already uses stable ids like `aws-s3`, `redux-rtk-query`, and `frontend-javascript-deep-dive`. The API therefore returns:

```json
{ "id": "aws-s3", "slug": "aws-s3", "uuid": "..." }
```

The database UUID remains the internal primary key. The frontend never needs to know it.

## Why sections are a table, not only JSON

The frontend needs sections for:

- right-side TOC
- search result jumps
- selected section export
- full-scroll lazy hydration

Keeping `topic_sections` as rows gives:

- section-level search
- selected-section export without fetching every topic body
- future progress tracking per section
- future notes/quizzes per section

## Why full markdown still lives on `topics`

A single-topic reader should be one fast row fetch plus section/source relationships. Keeping full markdown on `topics.body_markdown` keeps the main reading path simple and fast.

## Why source files are normalized

The current frontend has `sourceFiles: []`. A source can later be reused by many topics, have checksums, display paths, upload metadata, and ingestion history. That is why the API derives `sourceFiles` from `source_files` + `topic_source_links`.

## Scope for change

This schema can grow into:

- saved study paths using `note_collections`
- saved reader/export selections using `saved_selections`
- markdown import history using `content_import_batches`
- diagrams/images/code attachments using `assets`
- topic edit history using `topic_revisions`
- analytics from `search_events` and `export_jobs`
