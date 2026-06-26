# API Contract

Base path: `/api/v1`

## Bootstrap

`GET /bootstrap`

Use once on app load. Returns stats, group order, taxonomy, lightweight topics, and grouped tree.

## Topics

`GET /topics?limit=100&cursor=&group=&domain=&tag=&include_sections=true`

Cursor-paginated topic metadata.

`GET /topics/{topic_id}`

Full topic hydration. `topic_id` is the same string used by the frontend as `topic.id`.

`POST /topics/batch` and `POST /topics/hydrate`

Batch full-topic hydration.

```json
{
  "ids": ["aws-s3", "aws-lambda"],
  "include_sections": true,
  "include_sources": true,
  "include_assets": false,
  "include_section_bodies": true
}
```

## Search

`GET /search?q=lambda&limit=20&offset=0`

Offset-paginated section/topic search. Response items are shaped for the current Sidebar search UI.

## Export

`POST /exports/manifest`

Lightweight export preview.

`POST /exports/hydrate`

Full selected-topic hydration for PDF generation.

## Admin

All admin routes require `X-Admin-Token` or `Authorization: Bearer`.

`POST /admin/topics`

`PATCH /admin/topics/{topic_id}`

`DELETE /admin/topics/{topic_id}`

`POST /admin/topics/bulk-upsert`

`POST /admin/search/reindex`
