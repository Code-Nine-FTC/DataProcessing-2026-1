# -*- coding: utf-8 -*-
"""
Testes de integração para as novas ferramentas de camadas estaduais ambientais
e propriedades rurais com camadas ambientais.

Execução:
    pytest tests/test_camadas_estaduais_integration.py -v
"""
import pytest


def test_tool_functions_registradas() -> None:
    """Teste: validar que as novas ferramentas estão registradas."""
    from nlp_processor.tools import TOOL_FUNCTIONS
    
    assert "buscar_camadas_estaduais" in TOOL_FUNCTIONS, (
        "Ferramenta buscar_camadas_estaduais deve estar registrada"
    )
    assert "buscar_imoveis_com_camadas_estaduais" in TOOL_FUNCTIONS, (
        "Ferramenta buscar_imoveis_com_camadas_estaduais deve estar registrada"
    )
    
    # Validar que são funções callable
    assert callable(TOOL_FUNCTIONS["buscar_camadas_estaduais"])
    assert callable(TOOL_FUNCTIONS["buscar_imoveis_com_camadas_estaduais"])


def test_intencoes_novas_no_classificador() -> None:
    """Teste: validar que novas intenções estão no classificador."""
    from nlp_processor.pipeline.intent_classifier import INTENCOES
    
    assert "buscar_camadas_estaduais" in INTENCOES, (
        "Nova intenção 'buscar_camadas_estaduais' deve estar em INTENCOES"
    )
    assert "buscar_imoveis_em_camadas" in INTENCOES, (
        "Nova intenção 'buscar_imoveis_em_camadas' deve estar em INTENCOES"
    )


def test_intent_classification_camadas() -> None:
    """Teste: validar que a classificação de intenção funciona com novas intents."""
    from nlp_processor.pipeline.intent_classifier import get_classifier
    
    classifier = get_classifier()
    
    # Teste 1: Pergunta sobre camadas estaduais
    intencao1, confianca1 = classifier.predict("Quais são as camadas ambientais estaduais?")
    print(f"Intenção 1: {intencao1}, Confiança: {confianca1}")
    assert intencao1 == "buscar_camadas_estaduais", (
        f"Esperava 'buscar_camadas_estaduais', mas obteve: {intencao1}"
    )
    assert confianca1 > 0.5, f"Confiança deve ser > 0.5, obteve: {confianca1}"
    
    # Teste 2: Pergunta sobre imóveis em camadas
    intencao2, confianca2 = classifier.predict(
        "Quais propriedades rurais estão em zonas ambientais?"
    )
    print(f"Intenção 2: {intencao2}, Confiança: {confianca2}")
    assert intencao2 == "buscar_imoveis_em_camadas", (
        f"Esperava 'buscar_imoveis_em_camadas', mas obteve: {intencao2}"
    )
    assert confianca2 > 0.5, f"Confiança deve ser > 0.5, obteve: {confianca2}"


def test_intent_classification_rural_properties() -> None:
    """Teste: validar que intenção de propriedades rurais ainda funciona."""
    from nlp_processor.pipeline.intent_classifier import get_classifier
    
    classifier = get_classifier()
    
    intencao, confianca = classifier.predict("Mostre os imóveis rurais no estado de São Paulo")
    print(f"Intenção: {intencao}, Confiança: {confianca}")
    assert intencao == "buscar_imoveis_rurais", (
        f"Esperava 'buscar_imoveis_rurais', mas obteve: {intencao}"
    )


def test_query_builder_intents_mapeados() -> None:
    """Teste: validar que intents estão mapeadas no query builder."""
    from nlp_processor.pipeline.query_builder import _INTENT_MAP
    
    assert "buscar_camadas_estaduais" in _INTENT_MAP
    assert "buscar_imoveis_em_camadas" in _INTENT_MAP
    
    # Validar mapeamento correto
    assert _INTENT_MAP["buscar_camadas_estaduais"] == "buscar_camadas_estaduais"
    assert _INTENT_MAP["buscar_imoveis_em_camadas"] == "buscar_imoveis_com_camadas_estaduais"


def test_camada_estadual_ambiental_model_existe() -> None:
    """Teste: validar que o modelo CamadaEstadualAmbiental existe."""
    from models.db_model import CamadaEstadualAmbiental
    
    assert hasattr(CamadaEstadualAmbiental, "__tablename__")
    assert CamadaEstadualAmbiental.__tablename__ == "camada_estadual_ambiental"


def test_training_data_contem_novos_exemplos() -> None:
    """Teste: validar que train_data contém exemplos para novas intenções."""
    from nlp_processor.training.train_data import TRAIN_DATA
    
    # Contar exemplos por intenção
    intencoes_encontradas = {}
    for texto, intencao in TRAIN_DATA:
        if intencao not in intencoes_encontradas:
            intencoes_encontradas[intencao] = 0
        intencoes_encontradas[intencao] += 1
    
    assert "buscar_camadas_estaduais" in intencoes_encontradas, (
        "Deve haver exemplos de treinamento para 'buscar_camadas_estaduais'"
    )
    assert "buscar_imoveis_em_camadas" in intencoes_encontradas, (
        "Deve haver exemplos de treinamento para 'buscar_imoveis_em_camadas'"
    )
    
    # Validar quantidade de exemplos (pelo menos 10 cada)
    assert intencoes_encontradas["buscar_camadas_estaduais"] >= 10, (
        "Deve haver pelo menos 10 exemplos para 'buscar_camadas_estaduais'"
    )
    assert intencoes_encontradas["buscar_imoveis_em_camadas"] >= 10, (
        "Deve haver pelo menos 10 exemplos para 'buscar_imoveis_em_camadas'"
    )


def test_classifier_modelo_treinado() -> None:
    """Teste: validar que o classificador foi treinado corretamente."""
    from nlp_processor.pipeline.intent_classifier import get_classifier
    
    classifier = get_classifier()
    
    # Deve estar pronto
    assert classifier.is_ready(), "Classificador deve estar carregado"
    
    # Deve conseguir fazer predições
    intencao, confianca = classifier.predict("testar")
    assert isinstance(intencao, str)
    assert isinstance(confianca, float)
    assert 0 <= confianca <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

