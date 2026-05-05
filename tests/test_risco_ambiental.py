from models.db_model import classificar_nivel_risco_ambiental
from nlp_processor.pipeline.entity_extractor import Entidades
from nlp_processor.pipeline.response_formatter import formatar_resposta


def test_classificar_nivel_risco_ambiental_por_distancia():
    assert classificar_nivel_risco_ambiental(None) == "não classificado"
    assert classificar_nivel_risco_ambiental(100, False) == "muito alto"
    assert classificar_nivel_risco_ambiental(1000, False) == "alto"
    assert classificar_nivel_risco_ambiental(2500, False) == "médio"
    assert classificar_nivel_risco_ambiental(4500, False) == "baixo"
    assert classificar_nivel_risco_ambiental(6000, False) == "muito baixo"
    assert classificar_nivel_risco_ambiental(3000, True) == "muito alto"


def test_formatar_resposta_inclui_descricao_de_risco():
    texto = formatar_resposta(
        intencao="buscar_focos_queimada_imovel",
        entidades=Entidades(codigo_car="BR01231SP"),
        total_features=3,
        fontes=[],
        contexto_documental="",
        confianca=0.95,
        descricao_consulta="Nível de risco ambiental: alto.",
    )

    assert "Nível de risco ambiental: alto." in texto
