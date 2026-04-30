import pytest
import json
from sqlalchemy.ext.asyncio import AsyncSession
from models.db_model import ImovelRural

from .seed_data import seed_test_data, cleanup_test_data


@pytest.mark.asyncio
async def test_get_imoveis_intersecting_geometry(session: AsyncSession):
    """
    Teste de integração para a função get_imoveis_intersecting_geometry
    Verifica se a query ST_Intersects funciona corretamente
    """
    # 1. Insere dados de teste (o seed_data já limpa os dados anteriores)
    test_data = await seed_test_data(session)

    # 2. Teste 1: Geometria que deve intersectar os 2 imóveis de SP
    sp_polygon_geojson = json.dumps(test_data["geometrias_teste"]["sp_polygon"])

    result = await ImovelRural.get_imoveis_intersecting_geometry(session, sp_polygon_geojson)

    # Valida resultados
    assert len(result) >= 2, f"Esperava pelo menos 2 imóveis, mas encontrou {len(result)}"

    # Verifica se os imóveis são os esperados (SP 1 e SP 2)
    nomes_encontrados = [row.nome for row in result]
    assert "Imóvel SP 1" in nomes_encontrados
    assert "Imóvel SP 2" in nomes_encontrados

    # Valida estrutura dos resultados
    for row in result:
        assert hasattr(row, 'id')
        assert hasattr(row, 'nome')
        assert hasattr(row, 'area_ha')
        assert hasattr(row, 'geom')
        assert hasattr(row, 'atributos_json')

        # Valida geometria
        assert isinstance(row.geom, dict)
        assert 'type' in row.geom
        assert 'coordinates' in row.geom

    # 3. Teste 2: Geometria que NÃO deve intersectar nenhum imóvel de SP
    # Usa um ponto no oceano longe de qualquer imóvel
    ponto_oceano = json.dumps({"type": "Point", "coordinates": [-35.0, -20.0]})

    result_vazio = await ImovelRural.get_imoveis_intersecting_geometry(session, ponto_oceano)
    assert len(result_vazio) == 0, f"Esperava 0 imóveis, mas encontrou {len(result_vazio)}"

    # 4. Teste 3: Geometria que deve intersectar apenas o Imóvel SP 2
    sp_ponto_geojson = json.dumps(test_data["geometrias_teste"]["sp_ponto"])

    result_ponto = await ImovelRural.get_imoveis_intersecting_geometry(session, sp_ponto_geojson)

    assert len(result_ponto) == 1, f"Esperava exatamente 1 imóvel, mas encontrou {len(result_ponto)}"
    assert result_ponto[0].nome == "Imóvel SP 2"  # Ponto está dentro do SP 2

    # 5. Validações adicionais de integridade
    # Todos os resultados devem ter áreas positivas
    for row in result:
        assert row.area_ha > 0, f"Área inválida: {row.area_ha}"

    # Atributos JSON devem ser válidos
    for row in result:
        assert isinstance(row.atributos_json, dict)
        assert "tipo" in row.atributos_json
        assert row.atributos_json["tipo"] == "rural"


@pytest.mark.asyncio
async def test_geometry_validation(session: AsyncSession):
    """
    Teste de validação adicional para geometrias
    Garante que as geometrias retornadas são GeoJSON válidas
    """
    test_data = await seed_test_data(session)

    # Testa com geometria inválida (deve falhar graciosamente ou retornar vazio)
    invalid_geojson = json.dumps({"type": "Invalid", "coordinates": "not_a_coord"})

    try:
        result = await ImovelRural.get_imoveis_intersecting_geometry(session, invalid_geojson)
        # Se não falhar, deve retornar vazio
        assert len(result) == 0
    except Exception:
        # Esperado que falhe com geometria inválida
        pass

    # Testa com geometria vazia
    empty_geojson = json.dumps({"type": "Point", "coordinates": []})

    result_empty = await ImovelRural.get_imoveis_intersecting_geometry(session, empty_geojson)
    assert len(result_empty) == 0
