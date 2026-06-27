# app/schemas/db_schema.py

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Any | None = None
    primaryKey: bool = False


class ForeignKeySchema(BaseModel):
    name: str | None = None
    constrainedColumns: list[str] = []
    referredSchema: str | None = None
    referredTable: str | None = None
    referredColumns: list[str] = []


class IndexSchema(BaseModel):
    name: str | None = None
    columnNames: list[str | None] = []
    unique: bool = False


class UniqueConstraintSchema(BaseModel):
    name: str | None = None
    columnNames: list[str] = []


class PrimaryKeySchema(BaseModel):
    name: str | None = None
    columnNames: list[str] = []


class TableSchema(BaseModel):
    schemaName: str | None = None
    tableName: str
    columns: list[ColumnSchema]
    primaryKey: PrimaryKeySchema | None = None
    foreignKeys: list[ForeignKeySchema] = []
    indexes: list[IndexSchema] = []
    uniqueConstraints: list[UniqueConstraintSchema] = []


class DatabaseSchema(BaseModel):
    schemaName: str | None = None
    tables: list[TableSchema]