# -*- coding: utf-8 -*-
from fastapi import Depends, FastAPI

from api.router.admin import router as admin_router
from api.router.admin import ws_router as admin_ws_router
from api.router.analytics import router as analytics_router
from api.router.auth import router as auth_router
from api.router.chat import router as chat_router
from api.router.dashboard import router as dashboard_router
from api.router.geojson import router as geojson_router
from api.router.municipal import router as municipal_router
from api.router.spatial_validation import router as validation_router
from api.utils.auth import get_current_user


def define_routes(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(admin_ws_router)
    app.include_router(analytics_router)
    app.include_router(geojson_router)
    app.include_router(municipal_router)
    app.include_router(validation_router)
    app.include_router(dashboard_router)
    app.include_router(chat_router, dependencies=[Depends(get_current_user)])
    app.include_router(dashboard_router, dependencies=[Depends(get_current_user)])
