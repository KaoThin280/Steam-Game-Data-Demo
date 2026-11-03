"""Composition point for feature routers; keep business logic in services."""
from fastapi import APIRouter

from app.api.v1 import admin, agent_rpc, auth, dashboard, games


def build_api_router(*, enable_legacy_ai: bool = False) -> APIRouter:
    router = APIRouter()
    for feature in (auth, games, dashboard, agent_rpc, admin):
        router.include_router(feature.router)
    if enable_legacy_ai:
        # Load optional legacy implementations only when explicitly enabled.
        from app.api.v1 import ai_agent, chat, data_files

        for feature in (ai_agent, chat, data_files):
            router.include_router(feature.router)
    return router
