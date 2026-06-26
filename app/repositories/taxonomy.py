from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Domain, Group, Tag, Topic, TopicStatus, TopicTag
from app.schemas.taxonomy import TaxonomyItem


class TaxonomyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_groups(self) -> list[TaxonomyItem]:
        stmt = (
            select(Group, func.count(Topic.id).label("topic_count"))
            .join(Topic, Topic.group_id == Group.id, isouter=True)
            .where((Topic.id.is_(None)) | ((Topic.deleted_at.is_(None)) & (Topic.status == TopicStatus.published)))
            .group_by(Group.id)
            .order_by(Group.sort_order.asc(), Group.name.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            TaxonomyItem(
                id=row.Group.id,
                slug=row.Group.slug,
                name=row.Group.name,
                description=row.Group.description,
                sort_order=row.Group.sort_order,
                topic_count=row.topic_count,
            )
            for row in rows
        ]

    async def list_domains(self) -> list[TaxonomyItem]:
        stmt = (
            select(Domain, func.count(Topic.id).label("topic_count"))
            .join(Topic, Topic.domain_id == Domain.id, isouter=True)
            .where((Topic.id.is_(None)) | ((Topic.deleted_at.is_(None)) & (Topic.status == TopicStatus.published)))
            .group_by(Domain.id)
            .order_by(Domain.sort_order.asc(), Domain.name.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            TaxonomyItem(
                id=row.Domain.id,
                slug=row.Domain.slug,
                name=row.Domain.name,
                description=row.Domain.description,
                sort_order=row.Domain.sort_order,
                topic_count=row.topic_count,
            )
            for row in rows
        ]

    async def list_tags(self) -> list[TaxonomyItem]:
        stmt = (
            select(Tag, func.count(TopicTag.topic_id).label("topic_count"))
            .join(TopicTag, TopicTag.tag_id == Tag.id, isouter=True)
            .group_by(Tag.id)
            .order_by(Tag.name.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            TaxonomyItem(
                id=row.Tag.id,
                slug=row.Tag.slug,
                name=row.Tag.name,
                description=row.Tag.description,
                topic_count=row.topic_count,
            )
            for row in rows
        ]
