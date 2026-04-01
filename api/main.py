# -*- coding: utf-8 -*-
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config.lifespan import lifespan
from api.router.define_routes import define_routes


def get_application() -> FastAPI:
    app_ = FastAPI(
        docs_url="/",
        lifespan=lifespan,
    )
    app_.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app_


app = get_application()

define_routes(app)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info",
        reload=True,
    )