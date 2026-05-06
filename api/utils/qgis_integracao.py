# -*- coding: utf-8 -*-
"""Texto de apoio para levar o GeoJSON do campo «mapa» ao QGIS."""
from __future__ import annotations

from api.schemas.chat import QgisIntegracao


def montar_integracao_qgis() -> QgisIntegracao:
    return QgisIntegracao(
        crs="EPSG:4326",
        como_carregar_no_qgis=(
            "Use o objeto «mapa» (FeatureCollection) desta resposta ou, no histórico, "
            "`mensagens[n].mapa`. Salve esse JSON como arquivo .geojson em UTF-8 e no QGIS: "
            "Camada → Adicionar camada → Adicionar camada vetorial → selecione o arquivo. "
            "CRS da camada: WGS 84 (EPSG:4326)."
        ),
    )
