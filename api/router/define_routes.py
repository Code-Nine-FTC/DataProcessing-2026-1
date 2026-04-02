# -*- coding: utf-8 -*-
from fastapi import FastAPI
from api.router.municipal import router as municipal_router
from api.router.estado import router as estado_router
from api.router.imovel import router as imovel_router


def define_routes(app: FastAPI) -> None:
    app.include_router(municipal_router)
    app.include_router(estado_router)
    app.include_router(imovel_router)
