import asyncio
import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from shapely.geometry import shape, Point, Polygon

from models.db_model import ImovelRural  # Importa o modelo


async def seed_test_data(session: AsyncSession) -> Dict[str, Any]:
    """
    Insere dados de teste conhecidos para testes espaciais
    Retorna os dados inseridos para validação
    """
    # Limpa dados de teste anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Imóvel %'"))
    await session.commit()

    # Dados de teste conhecidos
    test_imoveis = [
        {
            "nome": "Imóvel SP 1",
            "area_ha": 100.5,
            "geom": shape({
                "type": "Polygon",
                "coordinates": [[
                    [-46.75, -23.65],
                    [-46.7, -23.65],
                    [-46.7, -23.6],
                    [-46.75, -23.6],
                    [-46.75, -23.65]
                ]]
            }),
            "centroid": shape({
                "type": "Point",
                "coordinates": [-46.725, -23.625]
            }),
            "atributos_json": {"tipo": "rural", "cultura": "soja"}
        },
        {
            "nome": "Imóvel SP 2",
            "area_ha": 75.3,
            "geom": shape({
                "type": "Polygon",
                "coordinates": [[
                    [-46.65, -23.55],
                    [-46.55, -23.55],
                    [-46.55, -23.45],
                    [-46.65, -23.45],
                    [-46.65, -23.55]
                ]]
            }),
            "centroid": shape({
                "type": "Point",
                "coordinates": [-46.6, -23.5]
            }),
            "atributos_json": {"tipo": "rural", "cultura": "milho"}
        },
        {
            "nome": "Imóvel RJ",
            "area_ha": 150.0,
            "geom": shape({
                "type": "Polygon",
                "coordinates": [[
                    [-43.2, -22.9],
                    [-43.1, -22.9],
                    [-43.1, -22.8],
                    [-43.2, -22.8],
                    [-43.2, -22.9]
                ]]
            }),
            "centroid": shape({
                "type": "Point",
                "coordinates": [-43.15, -22.85]
            }),
            "atributos_json": {"tipo": "rural", "cultura": "cafeicultura"}
        }
    ]

    # Insere imóveis
    inserted_imoveis = []
    for imovel_data in test_imoveis:
        # Converte geometria para WKT
        from geoalchemy2.functions import ST_AsText
        wkt_geom = imovel_data["geom"].wkt

        query = text("""
            INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
            VALUES (:nome, :area_ha, ST_GeomFromText(:geom, 4326), ST_GeomFromText(:centroid, 4326), :atributos_json)
            RETURNING id::text, nome_imovel, area_ha, ST_AsGeoJSON(geom)::json AS geom, atributos_json
        """)

        result = await session.execute(query, {
            "nome": imovel_data["nome"],
            "area_ha": imovel_data["area_ha"],
            "geom": wkt_geom,
            "centroid": imovel_data["centroid"].wkt,
            "atributos_json": json.dumps(imovel_data["atributos_json"])
        })

        inserted_imoveis.append(result.fetchone())
        await session.commit()

    # Retorna dados para validação
    return {
        "imoveis": inserted_imoveis,
        "geometrias_teste": {
            "sp_polygon": {
                "type": "Polygon",
                "coordinates": [[
                    [-46.75, -23.65],
                    [-46.55, -23.65],
                    [-46.55, -23.45],
                    [-46.75, -23.45],
                    [-46.75, -23.65]
                ]]
            },
            "sp_ponto": {"type": "Point", "coordinates": [-46.62, -23.52]},
            "rj_polygon": {
                "type": "Polygon",
                "coordinates": [[
                    [-43.25, -22.95],
                    [-43.05, -22.95],
                    [-43.05, -22.75],
                    [-43.25, -22.75],
                    [-43.25, -22.95]
                ]]
            }
        }
    }


async def cleanup_test_data(session: AsyncSession):
    """Limpa dados de teste (opcional)"""
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Imóvel %'"))
    await session.commit()


# Função utilitária para verificar se geometria contém ponto
def geometry_contains(geom_data: Dict, point_coords: List[float]) -> bool:
    """Verifica se uma geometria contém um ponto"""
    geom = shape(geom_data)
    return geom.contains(Point(point_coords[0], point_coords[1]))
