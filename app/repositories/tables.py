# app/repositories/schema.py

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tables import (
    ColumnSchema,
    DatabaseSchema,
    ForeignKeySchema,
    IndexSchema,
    PrimaryKeySchema,
    TableSchema,
    UniqueConstraintSchema,
)


SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "pg_toast",
}


class SchemaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_table_schema(
        self,
        *,
        table_name: str,
        schema_name: str | None = "public",
    ) -> TableSchema:
        return await self.session.run_sync(
            self._get_table_schema_sync,
            table_name,
            schema_name,
        )

    async def get_all_tables_schema(
        self,
        *,
        schema_name: str | None = "public",
        include_views: bool = False,
    ) -> DatabaseSchema:
        return await self.session.run_sync(
            self._get_all_tables_schema_sync,
            schema_name,
            include_views,
        )

    async def get_everything_schema(
        self,
        *,
        include_views: bool = False,
    ) -> list[DatabaseSchema]:
        return await self.session.run_sync(
            self._get_everything_schema_sync,
            include_views,
        )

    @staticmethod
    def _get_table_schema_sync(
        sync_session,
        table_name: str,
        schema_name: str | None,
    ) -> TableSchema:
        inspector = inspect(sync_session.connection())

        table_names = set(inspector.get_table_names(schema=schema_name))
        view_names = set(inspector.get_view_names(schema=schema_name))

        if table_name not in table_names and table_name not in view_names:
            raise ValueError(f"Table/view '{table_name}' not found in schema '{schema_name}'")

        return SchemaRepository._build_table_schema(
            inspector=inspector,
            table_name=table_name,
            schema_name=schema_name,
        )

    @staticmethod
    def _get_all_tables_schema_sync(
        sync_session,
        schema_name: str | None,
        include_views: bool,
    ) -> DatabaseSchema:
        inspector = inspect(sync_session.connection())

        table_names = inspector.get_table_names(schema=schema_name)

        if include_views:
            table_names += inspector.get_view_names(schema=schema_name)

        tables = [
            SchemaRepository._build_table_schema(
                inspector=inspector,
                table_name=table_name,
                schema_name=schema_name,
            )
            for table_name in table_names
        ]

        return DatabaseSchema(
            schemaName=schema_name,
            tables=tables,
        )

    @staticmethod
    def _get_everything_schema_sync(
        sync_session,
        include_views: bool,
    ) -> list[DatabaseSchema]:
        inspector = inspect(sync_session.connection())

        result: list[DatabaseSchema] = []

        for schema_name in inspector.get_schema_names():
            if schema_name in SYSTEM_SCHEMAS:
                continue

            table_names = inspector.get_table_names(schema=schema_name)

            if include_views:
                table_names += inspector.get_view_names(schema=schema_name)

            tables = [
                SchemaRepository._build_table_schema(
                    inspector=inspector,
                    table_name=table_name,
                    schema_name=schema_name,
                )
                for table_name in table_names
            ]

            result.append(
                DatabaseSchema(
                    schemaName=schema_name,
                    tables=tables,
                )
            )

        return result

    @staticmethod
    def _build_table_schema(
        *,
        inspector,
        table_name: str,
        schema_name: str | None,
    ) -> TableSchema:
        columns = []

        for col in inspector.get_columns(table_name, schema=schema_name):
            columns.append(
                ColumnSchema(
                    name=col["name"],
                    type=str(col["type"]),
                    nullable=bool(col["nullable"]),
                    default=col.get("default"),
                    primaryKey=bool(col.get("primary_key")),
                )
            )

        pk = inspector.get_pk_constraint(table_name, schema=schema_name)

        primary_key = PrimaryKeySchema(
            name=pk.get("name"),
            columnNames=pk.get("constrained_columns") or [],
        )

        foreign_keys = []

        for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
            foreign_keys.append(
                ForeignKeySchema(
                    name=fk.get("name"),
                    constrainedColumns=fk.get("constrained_columns") or [],
                    referredSchema=fk.get("referred_schema"),
                    referredTable=fk.get("referred_table"),
                    referredColumns=fk.get("referred_columns") or [],
                )
            )

        indexes = []

        for idx in inspector.get_indexes(table_name, schema=schema_name):
            indexes.append(
                IndexSchema(
                    name=idx.get("name"),
                    columnNames=idx.get("column_names") or [],
                    unique=bool(idx.get("unique")),
                )
            )

        unique_constraints = []

        for constraint in inspector.get_unique_constraints(table_name, schema=schema_name):
            unique_constraints.append(
                UniqueConstraintSchema(
                    name=constraint.get("name"),
                    columnNames=constraint.get("column_names") or [],
                )
            )

        return TableSchema(
            schemaName=schema_name,
            tableName=table_name,
            columns=columns,
            primaryKey=primary_key,
            foreignKeys=foreign_keys,
            indexes=indexes,
            uniqueConstraints=unique_constraints,
        )