from fastapi import Depends, APIRouter, Response
from app.repositories.tables import SchemaRepository
from app.schemas.tables import TableSchema, DatabaseSchema
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.core.security import require_admin

router = APIRouter(prefix="/schemas", tags=["schemas"], dependencies=[Depends(require_admin)])

@router.get("/table_schema", response_model=TableSchema)
async def get_table_schema(response: Response, table_name: str, schema_name:str | None = "public", session: AsyncSession = Depends(get_session)) -> list[TableSchema]:
    schema = await SchemaRepository(session=session).get_table_schema(table_name=table_name, schema_name=schema_name)
    return schema

@router.get("/all_table_schema", response_model=DatabaseSchema)
async def get_all_table_schema(response: Response, schema_name:str | None = "public", include_views: bool| None=False, session: AsyncSession = Depends(get_session)) -> list[DatabaseSchema]:
    schema = await SchemaRepository(session=session).get_all_tables_schema( schema_name=schema_name, include_views=include_views)
    return schema

@router.get("/everything_schema", response_model=DatabaseSchema)
async def get_everything_schema(response: Response, include_views: bool | None=False, session: AsyncSession = Depends(get_session)) -> list[DatabaseSchema]:
    schema = SchemaRepository(session=session).get_everything_schema(include_views=include_views)
    return schema