# -*- coding: utf-8 -*-
from fastapi import FastAPI

from api.router.analytics import router as analytics_router
from api.router.chat import router as chat_router
from api.router.geojson import router as geojson_router
from api.router.municipal import router as municipal_router
from api.router.spatial_validation import router as validation_router

def define_routes(app: FastAPI) -> None:
    app.include_router(analytics_router)
    app.include_router(chat_router)
    app.include_router(geojson_router)
    app.include_router(municipal_router)
    app.include_router(validation_router)
