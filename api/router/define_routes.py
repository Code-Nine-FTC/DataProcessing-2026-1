# -*- coding: utf-8 -*-
from fastapi import FastAPI
from api.router.municipal import router as municipal_router


from api.router.chat import router as chat_router


from api.router.chat import router as chat_router


def define_routes(app: FastAPI) -> None:
    app.include_router(municipal_router)
    app.include_router(chat_router)
