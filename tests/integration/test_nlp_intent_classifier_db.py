from datetime import date

import pytest
from sqlalchemy import select, text

from models.db_model import (
    ConsultaUsuario,
    ImovelRural,
    IntencaoConsulta,
    Municipio,
    QueimadaEvento,
)
from nlp_processor.pipeline.entity_extractor import Entidades, extrair_entidades
from nlp_processor.pipeline.query_builder import executar_consulta

pytestmark = pytest.mark.integration


class TestEntityExtractionWithDB:
    """Entity extraction (regex + gazetteer) + DB query — sem ML, sem mocks."""

    async def test_extrair_municipio_da_base_gazetteer(self, db_session):
        ent = extrair_entidades("Queimadas em Caçapava?")
        assert ent.municipio == "Cacapava"

    async def test_extrair_municipio_carregado_do_banco(self, db_session):
        municipios = await _carregar_municipios(db_session)
        ent = extrair_entidades("Queimadas em Jacareí?", municipios_extras=municipios)
        assert ent.municipio == "Jacarei"

    async def test_entidade_municipio_consulta_queimadas(self, db_session):
        municipios = await _carregar_municipios(db_session)
        ent = extrair_entidades("Queimadas em Jacareí?", municipios_extras=municipios)
        assert ent.municipio is not None

        stmt = (
            select(QueimadaEvento)
            .join(Municipio, QueimadaEvento.municipio_id == Municipio.id)
            .where(Municipio.nome == "Jacareí")
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) == 2

    async def test_entidade_municipio_consulta_imoveis(self, db_session):
        ent = extrair_entidades("Imóveis em São José dos Campos?")
        assert ent.municipio == "Sao Jose Dos Campos"

        stmt = (
            select(ImovelRural)
            .join(Municipio, ImovelRural.municipio_id == Municipio.id)
            .where(Municipio.nome == "São José dos Campos")
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].codigo_car == "SP-350000-000000000001"

    async def test_extrair_datas_e_consultar(self, db_session):
        ent = extrair_entidades("Queimadas de 01/03/2026 até 31/03/2026 em Caçapava?")
        assert ent.data_inicio == "2026-03-01"
        assert ent.data_fim == "2026-03-31"
        assert ent.municipio == "Cacapava"

        data_inicio = date.fromisoformat(ent.data_inicio)
        data_fim = date.fromisoformat(ent.data_fim)
        stmt = (
            select(QueimadaEvento)
            .join(Municipio, QueimadaEvento.municipio_id == Municipio.id)
            .where(Municipio.nome == "Caçapava")
            .where(QueimadaEvento.data_ocorrencia >= data_inicio)
            .where(QueimadaEvento.data_ocorrencia <= data_fim)
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) == 1

    async def test_extrair_codigo_car_e_consultar_imovel(self, db_session):
        ent = extrair_entidades("Passivos do imóvel SP-350000-000000000001?")
        assert ent.codigo_car == "SP-350000-000000000001"

        imovel = (
            await db_session.execute(
                select(ImovelRural).where(ImovelRural.codigo_car == ent.codigo_car)
            )
        ).scalar_one_or_none()
        assert imovel is not None
        assert imovel.nome_imovel == "Fazenda Teste Alpha"


class TestQueryBuilderWithDB:
    """Query builder executar_consulta com intenções específicas — sem ML."""

    async def test_buscar_queimadas_por_municipio(self, db_session):
        ent = Entidades(municipio="Jacareí")
        resultado = await executar_consulta(
            session=db_session,
            intencao="buscar_queimadas",
            entidades=ent,
            query_embedding=[],
        )

        assert len(resultado["features"]) == 2
        for f in resultado["features"]:
            assert f["properties"]["tipo"] == "queimada"
        assert resultado["sql_executado"] is not None

    async def test_buscar_queimadas_sem_municipio_retorna_todas(self, db_session):
        ent = Entidades()
        resultado = await executar_consulta(
            session=db_session,
            intencao="buscar_queimadas",
            entidades=ent,
            query_embedding=[],
        )

        assert len(resultado["features"]) == 5

    async def test_buscar_queimadas_sem_resultado(self, db_session):
        ent = Entidades(municipio="MunicipioInexistente")
        resultado = await executar_consulta(
            session=db_session,
            intencao="buscar_queimadas",
            entidades=ent,
            query_embedding=[],
        )

        assert len(resultado["features"]) == 0
        assert resultado["descricao"] is not None

    async def test_buscar_imoveis_rurais_por_codigo_car(self, db_session):
        ent = Entidades(codigo_car="SP-350000-000000000002")
        resultado = await executar_consulta(
            session=db_session,
            intencao="buscar_imoveis_rurais",
            entidades=ent,
            query_embedding=[],
        )

        assert len(resultado["features"]) == 1
        props = resultado["features"][0]["properties"]
        assert props["nome_imovel"] == "Sitio Teste Beta"
        assert props["codigo_car"] == "SP-350000-000000000002"

    async def test_buscar_imoveis_rurais_por_municipio(self, db_session):
        ent = Entidades(municipio="São José dos Campos")
        resultado = await executar_consulta(
            session=db_session,
            intencao="buscar_imoveis_rurais",
            entidades=ent,
            query_embedding=[],
        )

        nomes = [f["properties"].get("nome_imovel") for f in resultado["features"]]
        assert "Fazenda Teste Alpha" in nomes

    async def test_intencao_fora_escopo_retorna_vazio(self, db_session):
        ent = Entidades()
        resultado = await executar_consulta(
            session=db_session,
            intencao="fora_escopo",
            entidades=ent,
            query_embedding=[],
        )

        assert resultado["features"] == []
        assert resultado["fontes"] == []


class TestIntentPersistence:
    """Persistência e consulta de metadados de classificação no banco."""

    async def test_criar_e_consultar_intencao_catalogo(self, db_session):
        intencao = IntencaoConsulta(nome="buscar_queimadas")
        db_session.add(intencao)
        await db_session.flush()

        stmt = select(IntencaoConsulta).where(
            IntencaoConsulta.nome == "buscar_queimadas"
        )
        result = (await db_session.execute(stmt)).scalar_one()
        assert result.nome == "buscar_queimadas"
        assert result.id is not None

    async def test_consulta_usuario_com_intencao_persistida(self, db_session):
        intencao = IntencaoConsulta(nome="buscar_queimadas")
        db_session.add(intencao)
        await db_session.flush()

        consulta = ConsultaUsuario(
            pergunta="Queimadas em Jacareí?",
            intencao_detectada="buscar_queimadas",
            intencao_score=0.95,
            intencao_id=intencao.id,
            turno=1,
        )
        db_session.add(consulta)
        await db_session.flush()

        stmt = select(ConsultaUsuario).where(
            ConsultaUsuario.intencao_id == intencao.id
        )
        result = (await db_session.execute(stmt)).scalar_one()
        assert result.pergunta == "Queimadas em Jacareí?"
        assert result.intencao_score == 0.95

    async def test_filtrar_consultas_por_intencao_score(self, db_session):
        dados = [
            ("buscar_queimadas", 0.95, 1),
            ("buscar_queimadas", 0.50, 2),
            ("buscar_imoveis_rurais", 0.88, 3),
        ]
        for intencao, score, turno in dados:
            int_obj = IntencaoConsulta(nome=intencao)
            db_session.add(int_obj)
            await db_session.flush()
            consulta = ConsultaUsuario(
                pergunta=f"Pergunta {turno}",
                intencao_detectada=intencao,
                intencao_score=score,
                intencao_id=int_obj.id,
                turno=turno,
            )
            db_session.add(consulta)
        await db_session.flush()

        stmt = (
            select(ConsultaUsuario)
            .where(ConsultaUsuario.intencao_score >= 0.80)
            .order_by(ConsultaUsuario.intencao_score.desc())
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) >= 2
        for r in rows:
            assert r.intencao_score >= 0.80


async def _carregar_municipios(db_session) -> list[str]:
    from nlp_processor.pipeline.preprocessor import normalizar
    stmt = select(Municipio.nome).where(Municipio.nome.is_not(None))
    result = await db_session.execute(stmt)
    return sorted({normalizar(nome) for (nome,) in result.all()})
