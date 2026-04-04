# -*- coding: utf-8 -*-
from fastapi import FastAPI, APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.router.analytics import router as analytics_router
from api.router.chat import router as chat_router
from api.router.geojson import router as geojson_router
from api.router.municipal import router as municipal_router
from api.utils.validation_service import validate_database_crs_integrity
from models.database import SessionConnection

validation_router = APIRouter(prefix="/health/spatial", tags=["Health & Spatial Validation"])


@validation_router.get("/")
async def check_spatial_health(auto_correct: bool = False, db: AsyncSession = Depends(SessionConnection.session)):
    """
    Verifica a saúde de todas as geometrias do banco de dados e padronização EPSG:4326.
    Retorna o status true se todas estiverem OGC Compliant e com SRID certo.
    """
    is_healthy = await validate_database_crs_integrity(db, auto_correct=auto_correct)
    return {"status": "ok" if is_healthy else "issues_found", "auto_corrected": auto_correct}


def define_routes(app: FastAPI) -> None:
    app.include_router(analytics_router)
    app.include_router(chat_router)
    app.include_router(geojson_router)
    app.include_router(municipal_router)
    app.include_router(validation_router)
