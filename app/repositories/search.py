from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import SearchEvent
from app.schemas.search import SearchResult, SearchSuggestResult


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        *,
        query: str,
        limit: int = 20,
        offset: int = 0,
        group: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        log_event: bool = True,
    ) -> tuple[list[SearchResult], int]:
        started = time.perf_counter()
        params = {
            "q": query,
            "limit": limit,
            "offset": offset,
            "group": group,
            "domain": domain,
            "tag": tag,
        }
        sql = text(
            """
            with q as (select websearch_to_tsquery('english', :q) as query),
            filtered_topics as (
                select t.*,
                       g.name as group_name,
                       g.slug as group_slug,
                       d.name as domain_name,
                       d.slug as domain_slug
                from topics t
                left join groups g on g.id = t.group_id
                left join domains d on d.id = t.domain_id
                where t.deleted_at is null
                  and t.status = 'published'
                  and (:group is null or g.slug = :group)
                  and (:domain is null or d.slug = :domain)
                  and (
                    :tag is null or exists (
                      select 1 from topic_tags tt
                      join tags tg on tg.id = tt.tag_id
                      where tt.topic_id = t.id and tg.slug = :tag
                    )
                  )
            ),
            topic_hits as (
                select 'topic'::text as kind,
                       ft.slug as topic_slug,
                       ft.title as topic_title,
                       null::text as section_slug,
                       null::text as section_title,
                       ft.group_name,
                       ft.domain_name,
                       ts_rank_cd(ft.search_vector, q.query) as rank,
                       ts_headline('english', concat_ws(' ', ft.title, ft.summary, ft.body_plain_text), q.query,
                           'StartSel=<mark>, StopSel=</mark>, MaxWords=32, MinWords=12') as snippet,
                       ft.body_hash
                from filtered_topics ft, q
                where ft.search_vector @@ q.query
            ),
            section_hits as (
                select 'section'::text as kind,
                       ft.slug as topic_slug,
                       ft.title as topic_title,
                       s.slug as section_slug,
                       s.title as section_title,
                       ft.group_name,
                       ft.domain_name,
                       ts_rank_cd(s.search_vector, q.query) as rank,
                       ts_headline('english', concat_ws(' ', s.title, s.body_plain_text), q.query,
                           'StartSel=<mark>, StopSel=</mark>, MaxWords=32, MinWords=12') as snippet,
                       s.body_hash
                from filtered_topics ft
                join topic_sections s on s.topic_id = ft.id and s.deleted_at is null, q
                where s.search_vector @@ q.query
            ),
            unioned as (
                select * from topic_hits
                union all
                select * from section_hits
            ),
            counted as (
                select count(*) as total from unioned
            )
            select u.*, c.total
            from unioned u cross join counted c
            order by u.rank desc, u.topic_title asc, u.section_title asc nulls first
            limit :limit offset :offset
            """
        )
        rows = (await self.session.execute(sql, params)).mappings().all()
        total = int(rows[0]["total"]) if rows else 0
        results = []
        for row in rows:
            section_path = [part for part in [row["group_name"], row["topic_title"], row["section_title"]] if part]
            results.append(
                SearchResult(
                    kind=row["kind"],
                    topicId=row["topic_slug"],
                    topicTitle=row["topic_title"],
                    sectionId=row["section_slug"] or "overview",
                    sectionTitle=row["section_title"] or row["topic_title"],
                    sectionPath=section_path,
                    group=row["group_name"],
                    domain=row["domain_name"],
                    rank=float(row["rank"] or 0),
                    snippet=row["snippet"] or "",
                    bodyHash=row["body_hash"],
                    topic_slug=row["topic_slug"],
                    section_slug=row["section_slug"],
                )
            )
        if log_event:
            duration_ms = round((time.perf_counter() - started) * 1000)
            self.session.add(SearchEvent(query=query, result_count=total, duration_ms=duration_ms))
            await self.session.commit()
        return results, total

    async def suggest(self, *, query: str, limit: int = 10) -> list[SearchSuggestResult]:
        like = f"%{query.lower()}%"
        sql = text(
            """
            select title as label, slug as value, 'topic' as kind
            from topics
            where deleted_at is null and status = 'published' and lower(title) like :like
            union all
            select name as label, slug as value, 'tag' as kind from tags where lower(name) like :like
            union all
            select name as label, slug as value, 'group' as kind from groups where lower(name) like :like
            union all
            select name as label, slug as value, 'domain' as kind from domains where lower(name) like :like
            limit :limit
            """
        )
        rows = (await self.session.execute(sql, {"like": like, "limit": limit})).mappings().all()
        return [SearchSuggestResult(label=row["label"], value=row["value"], kind=row["kind"]) for row in rows]
