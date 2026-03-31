# -*- coding: utf-8 -*-
from fastapi import FastAPI, APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
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
    app.include_router(validation_router)
