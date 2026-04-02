# -*- coding: utf-8 -*-
from fastapi import FastAPI
from api.router.municipal import router as municipal_router
from api.router.geojson import router as geojson_router


def define_routes(app: FastAPI) -> None:
    app.include_router(municipal_router)
    app.include_router(geojson_router)