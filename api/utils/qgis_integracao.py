# -*- coding: utf-8 -*-
"""Texto de apoio para levar o GeoJSON desta resposta ao QGIS (URL HTTP ou campo «mapa»)."""
from __future__ import annotations

from uuid import UUID

from api.schemas.chat import QgisIntegracao


def montar_integracao_qgis(resposta_id: UUID) -> QgisIntegracao:
    path = f"/chat/resposta/{resposta_id}/geojson"
    return QgisIntegracao(
        crs="EPSG:4326",
        geojson_url_path=path,
        como_carregar_no_qgis=(
            "No QGIS: Camada → Adicionar camada → Adicionar camada vetorial → em «Fonte» informe a URI completa "
            "(URL base da API + o valor de «geojson_url_path»). É o mesmo GeoJSON do campo «mapa», servido pelo servidor "
            "sem reprocessar o NLP. CRS: WGS 84 (EPSG:4326). Alternativa: grave o objeto «mapa» como arquivo .geojson "
            "(UTF-8) e abra o arquivo."
        ),
    )
