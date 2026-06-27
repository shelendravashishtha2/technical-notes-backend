from fastapi import APIRouter

from app.api.v1.routes import admin, bootstrap, exports, health, search, taxonomy, topics, tables

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(bootstrap.router)
api_router.include_router(topics.router)
api_router.include_router(search.router)
api_router.include_router(taxonomy.router)
api_router.include_router(exports.router)
api_router.include_router(admin.router)
api_router.include_router(tables.router)