from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, chat, conversations, datasets, explore, graph, ingestion, status

api_router = APIRouter()
api_router.include_router(status.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(conversations.router)
api_router.include_router(datasets.router)
api_router.include_router(ingestion.router)
api_router.include_router(graph.router)
api_router.include_router(explore.router)
api_router.include_router(admin.router)
