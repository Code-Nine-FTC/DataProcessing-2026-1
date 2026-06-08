# -*- coding: utf-8 -*-
"""
Dados de treinamento anotados para o classificador de intenções.
Cada entrada é (texto_exemplo, lista_de_intencoes).

Modificado para suporte nativo a Multi-Label (Múltiplas Intenções por frase).
Para treinar, execute:
    python -m nlp_processor.training.train
"""

# A tipagem agora aceita explicitamente uma lista de strings para as intenções
TRAIN_DATA: list[tuple[str, list[str]]] = [

    # =========================================================================
    # ---- EXEMPLOS ORIGINAIS CONVERTIDOS PARA MULTI-LABEL ----
    # =========================================================================

    # ---- buscar_queimadas ----
    ("Quais foram os focos de incêndio em Ribeirão Preto em 2024?", ["buscar_queimadas"]),
    ("Mostra os focos de queimada no estado de São Paulo", ["buscar_queimadas"]),
    ("Quantos focos de queimada foram registrados em 2023?", ["buscar_queimadas"]),
    ("Incêndios florestais em Campinas no último ano", ["buscar_queimadas"]),
    ("Mapa de focos de calor em São Paulo", ["buscar_queimadas"]),
    ("Quero ver as queimadas detectadas pelo satélite AQUA", ["buscar_queimadas"]),
    ("Focos de incêndio em Presidente Prudente", ["buscar_queimadas"]),
    ("Onde ocorreram queimadas em 2025?", ["buscar_queimadas"]),
    ("Queimadas registradas entre janeiro e março de 2024", ["buscar_queimadas"]),
    ("Histórico de incêndios em Sorocaba", ["buscar_queimadas"]),
    ("Focos de calor detectados pelo VIIRS", ["buscar_queimadas"]),
    ("Houve queimadas em Bauru recentemente?", ["buscar_queimadas"]),

    # ---- buscar_desmatamentos ----
    ("Exibir alertas de desmatamento em São José dos Campos", ["buscar_desmatamentos"]),
    ("Onde houve perda de vegetação nativa em 2024?", ["buscar_desmatamentos"]),
    ("Alertas do DETER para o município de Sorocaba", ["buscar_desmatamentos"]),
    ("Quero ver o desmatamento acumulado no estado", ["buscar_desmatamentos"]),
    ("Dados de supressão de vegetação em 2023", ["buscar_desmatamentos"]),
    ("Quais áreas foram desmatadas recentemente em Botucatu?", ["buscar_desmatamentos"]),
    ("Mapa de desmatamento ilegal em São Paulo", ["buscar_desmatamentos"]),
    ("Alertas de perda de floresta no Vale do Paraíba", ["buscar_desmatamentos"]),
    ("Corte raso detectado por satélite em Santos", ["buscar_desmatamentos"]),
    ("Taxa de desmatamento no município de Franca", ["buscar_desmatamentos"]),

    # ---- buscar_unidades_conservacao ----
    ("Quais são as unidades de conservação em Ubatuba?", ["buscar_unidades_conservacao"]),
    ("Mostre os parques estaduais no estado de São Paulo", ["buscar_unidades_conservacao"]),
    ("Exista alguma APA ou reserva biológica em Jundiaí?", ["buscar_unidades_conservacao"]),
    ("Mapa das Unidades de Conservação Federais em SP", ["buscar_unidades_conservacao"]),
    ("Quero ver o perímetro das áreas protegidas em Peruíbe", ["buscar_unidades_conservacao"]),
    ("Lista de florestas estaduais e estações ecológicas", ["buscar_unidades_conservacao"]),
    ("Quais RPPNs estão cadastradas em São Francisco Xavier?", ["buscar_unidades_conservacao"]),

    # ---- buscar_terras_indigenas ----
    ("Localizar terras indígenas no estado de São Paulo", ["buscar_terras_indigenas"]),
    ("Onde ficam as comunidades guarani em Peruíbe?", ["buscar_terras_indigenas"]),
    ("Mapa das áreas indígenas homologadas pela FUNAI", ["buscar_terras_indigenas"]),
    ("Quais são as TIs na região do Vale do Ribeira?", ["buscar_terras_indigenas"]),
    ("Terras indígenas em processo de demarcação em SP", ["buscar_terras_indigenas"]),
    ("Buscar reservas indígenas perto de Mongaguá", ["buscar_terras_indigenas"]),

    # ---- buscar_assentamentos ----
    ("Quais são os assentamentos do INCRA em Promissão?", ["buscar_assentamentos"]),
    ("Mapa de assentamentos rurais no Pontal do Paranapanema", ["buscar_assentamentos"]),
    ("Projetos de assentamento estadual cadastrados pelo ITESP", ["buscar_assentamentos"]),
    ("Onde ficam os assentamentos de reforma agrária em SP?", ["buscar_assentamentos"]),
    ("Buscar áreas de assentamento no município de Euclides da Cunha Paulista", ["buscar_assentamentos"]),

    # ---- buscar_quilombolas ----
    ("Exibir territórios quilombolas em Eldorado", ["buscar_quilombolas"]),
    ("Onde ficam as comunidades quilombolas no Vale do Ribeira?", ["buscar_quilombolas"]),
    ("Mapa de terras de comunidades tradicionais de quilombo em SP", ["buscar_quilombolas"]),
    ("Quais quilombos já possuem título emitido pelo INCRA?", ["buscar_quilombolas"]),
    ("Buscar áreas quilombolas reconhecidas em Registro", ["buscar_quilombolas"]),

    # ---- buscar_imoveis_rurais ----
    ("Buscar imóveis rurais cadastrados no CAR em Piracicaba", ["buscar_imoveis_rurais"]),
    ("Quero ver o desenho da fazenda com o recibo SP-3550308-...", ["buscar_imoveis_rurais"]),
    ("Visualizar o perímetro do imóvel rural no SICAR", ["buscar_imoveis_rurais"]),
    ("Dados de propriedades rurais cadastradas em Marília", ["buscar_imoveis_rurais"]),
    ("Mapa de cadastros ambientais rurais ativos em Limeira", ["buscar_imoveis_rurais"]),

    # ---- buscar_imoveis_queimada ----
    ("Quais imóveis rurais foram atingidos por queimadas em 2024?", ["buscar_imoveis_queimada"]),
    ("Fazendas em Ribeirão Preto que registraram focos de incêndio", ["buscar_imoveis_queimada"]),
    ("Buscar CAR de propriedades com cicatrizes de fogo em SP", ["buscar_imoveis_queimada"]),

    # ---- buscar_imoveis_desmatamento ----
    ("Quais propriedades rurais possuem alertas de desmatamento?", ["buscar_imoveis_desmatamento"]),
    ("Imóveis cadastrados no CAR com supressão vegetal ilegal em Sorocaba", ["buscar_imoveis_desmatamento"]),
    ("Listar fazendas em Campinas com alertas DETER dentro do perímetro", ["buscar_imoveis_desmatamento"]),

    # ---- buscar_imoveis_quilombo ----
    ("Quais propriedades rurais privadas sobrepõem territórios quilombolas?", ["buscar_imoveis_quilombo"]),
    ("Imóveis do CAR que cruzam com áreas de quilombo em Eldorado", ["buscar_imoveis_quilombo"]),

    # ---- buscar_imoveis_ti ----
    ("Existem imóveis rurais invadindo terras indígenas em SP?", ["buscar_imoveis_ti"]),
    ("Buscar cadastros do SICAR que intersectam a TI Tekoa Pyau", ["buscar_imoveis_ti"]),

    # ---- buscar_camadas_estaduais ----
    ("Exibir mapa de zoneamento ambiental do estado de São Paulo", ["buscar_camadas_estaduais"]),
    ("Quais são os limites das bacias hidrográficas paulistas?", ["buscar_camadas_estaduais"]),
    ("Camada geomorfológica ou de vulnerabilidade climática da SIMA", ["buscar_camadas_estaduais"]),

    # ---- buscar_imoveis_em_camadas ----
    ("Quais fazendas estão dentro de áreas de restrição ambiental estadual?", ["buscar_imoveis_em_camadas"]),
    ("Imóveis do CAR localizados na faixa de amortecimento de parques", ["buscar_imoveis_em_camadas"]),

    # ---- buscar_documentos ----
    ("Quais são as regras para o licenciamento ambiental de desmatamento?", ["buscar_documentos"]),
    ("Como funciona a regularização de passivo ambiental no PRA?", ["buscar_documentos"]),
    ("Legislação sobre queima controlada de cana-de-açúcar em SP", ["buscar_documentos"]),
    ("Manuais de restauração florestal da Secretaria de Meio Ambiente", ["buscar_documentos"]),

    # ---- fora_escopo ----
    ("Qual a previsão do tempo para a capital amanhã?", ["fora_escopo"]),
    ("Quais são as notícias sobre futebol em Campinas?", ["fora_escopo"]),
    ("Queimadas no Pantanal mato-grossense", ["fora_escopo"]),
    ("Qual o preço do boi gordo hoje?", ["fora_escopo"]),
    ("Me fale sobre a história do Brasil", ["fora_escopo"]),
    ("Dados ambientais do estado do Paraná", ["fora_escopo"]),
    ("Terras indígenas no Pará", ["fora_escopo"]),
    ("Como está a seca no Nordeste?", ["fora_escopo"]),
    ("Dados climáticos do Rio de Janeiro", ["fora_escopo"]),
    ("Qual o partido político mais votado em SP?", ["fora_escopo"]),
    ("Cotação do dólar hoje", ["fora_escopo"]),
    ("Unidades de conservação no Amazonas", ["fora_escopo"]),
    ("queimadas no cerrado goias", ["fora_escopo"]),
    ("desmatamento amazonia para 2024", ["fora_escopo"]),
    ("terras indigenas mato grosso", ["fora_escopo"]),
    ("assentamentos incra minas gerais", ["fora_escopo"]),
    ("unidades conservacao rio de janeiro", ["fora_escopo"]),
    ("previsao chuva campinas semana", ["fora_escopo"]),
    ("preco soja commodities hoje", ["fora_escopo"]),
    ("eleicoes municipais sp resultado", ["fora_escopo"]),
    ("temperatura media ribeirao preto", ["fora_escopo"]),
    ("dados demograficos sao paulo ibge", ["fora_escopo"]),
    ("queda energia eletrica campinas", ["fora_escopo"]),

    # =========================================================================
    # ---- INTENÇÕES QUE ESTAVAM AUSENTES / CORREÇÕES ----
    # =========================================================================

    # ---- buscar_focos_queimada_imovel ----
    ("Quais foram os focos de queimada detectados no imóvel SP000123456?", ["buscar_focos_queimada_imovel"]),
    ("Histórico de incêndios dentro da propriedade CAR SP999888777", ["buscar_focos_queimada_imovel"]),
    ("Houve algum foco de calor registrado na minha fazenda SP000123456?", ["buscar_focos_queimada_imovel"]),
    ("Satélite detectou fogo dentro do imóvel rural SP111222333?", ["buscar_focos_queimada_imovel"]),
    ("Quero ver o mapa de focos de incêndio no CAR SP000123456", ["buscar_focos_queimada_imovel"]),
    ("Quantas queimadas atingiram o imóvel SP000123456 em 2024?", ["buscar_focos_queimada_imovel"]),
    ("focos de calor detectados no perimetro do imovel SP555444333", ["buscar_focos_queimada_imovel"]),
    ("sicar SP000123456 teve fogo recentemente?", ["buscar_focos_queimada_imovel"]),

    # ---- buscar_maiores_quantidades ----
    ("Quais são os municípios com maior número de focos de queimada em SP?", ["buscar_maiores_quantidades"]),
    ("Qual a região administrativa que mais desmatou em 2024?", ["buscar_maiores_quantidades"]),
    ("Mostre o ranking das maiores propriedades rurais por área em Campinas", ["buscar_maiores_quantidades"]),
    ("Quais cidades paulistas possuem mais terras indígenas homologadas?", ["buscar_maiores_quantidades"]),
    ("Quais os municípios com maior área de assentamento do INCRA em SP?", ["buscar_maiores_quantidades"]),
    ("Ranking de desmatamento DETER por região administrativa", ["buscar_maiores_quantidades"]),
    ("quais as RAs com maior quantidade de quilombolas no estado?", ["buscar_maiores_quantidades"]),
    ("lista de cidades com mais alertas de supressao vegetal", ["buscar_maiores_quantidades"]),
    ("maiores focos de incendio por municipio em sao paulo", ["buscar_maiores_quantidades"]),
    ("Quais os municípios com maiores quantidades de queimadas na RA de Sorocaba?", ["buscar_maiores_quantidades"]),
    ("ranking de desmatamento na regiao administrativa de marilia", ["buscar_maiores_quantidades"]),
    ("cidades com mais imoveis rurais na ra de campinas", ["buscar_maiores_quantidades"]),
    ("maiores indices de focos de calor na racam", ["buscar_maiores_quantidades"]),

    # ---- buscar_passivos_imovel ----
    ("Buscar passivos ambientais do imóvel rural SP000123456", ["buscar_passivos_imovel"]),
    ("O imóvel CAR SP999888777 possui algum passivo ou embargo?", ["buscar_passivos_imovel"]),
    ("Quais as irregularidades e passivos ambientais na fazenda SP111222333?", ["buscar_passivos_imovel"]),
    ("relatorio de passivos ambientais para o sicar SP000123456", ["buscar_passivos_imovel"]),
    ("verificar se a propriedade SP555444333 tem passivo de desmatamento", ["buscar_passivos_imovel"]),

    # =========================================================================
    # ---- NOVO COMPORTAMENTO: PERGUNTAS DE MULTI-INTENÇÃO REAL ----
    # =========================================================================

    # ---- Cruzamento: Queimadas + Desmatamento ----
    ("Quero ver o mapa de queimadas e os alertas de desmatamento em Campinas", ["buscar_queimadas", "buscar_desmatamentos"]),
    ("Mostre os focos de incêndio combinados com a supressão vegetal recente", ["buscar_queimadas", "buscar_desmatamentos"]),
    ("Houve fogo ou corte de vegetação nativa em Sorocaba este ano?", ["buscar_queimadas", "buscar_desmatamentos"]),

    # ---- Cruzamento: Queimadas + Terras Indígenas ----
    ("Focos de incêndio detectados dentro de terras indígenas em SP", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Mapa de calor sobreposto aos territórios indígenas do Vale do Ribeira", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Quais TIs em São Paulo estão sofrendo com queimadas agora?", ["buscar_queimadas", "buscar_terras_indigenas"]),

    # ---- Cruzamento: Desmatamento + Unidades de Conservação ----
    ("Alertas de desmatamento do DETER dentro de parques estaduais", ["buscar_desmatamentos", "buscar_unidades_conservacao"]),
    ("Quais unidades de conservação sofreram supressão de vegetação?", ["buscar_desmatamentos", "buscar_unidades_conservacao"]),
    ("Monitoramento de corte ilegal em APAs no litoral paulista", ["buscar_desmatamentos", "buscar_unidades_conservacao"]),

    # ---- Cruzamento: Queimadas + Assentamentos / Quilombolas ----
    ("Focos de calor em áreas de assentamento rural no Pontal do Paranapanema", ["buscar_queimadas", "buscar_assentamentos"]),
    ("Houve registro de fogo em comunidades quilombolas de Eldorado?", ["buscar_queimadas", "buscar_quilombolas"]),
    ("Incêndios florestais perto de territórios de quilombo e assentados", ["buscar_queimadas", "buscar_quilombolas", "buscar_assentamentos"]),

    # ---- Cruzamento: Imóveis Rurais + Múltiplas Camadas Ambientais ----
    ("Quais imóveis do CAR estão em áreas protegidas ou territórios quilombolas?", ["buscar_imoveis_rurais", "buscar_unidades_conservacao", "buscar_quilombolas"]),
    ("Sobreposição de propriedades rurais com TIs e UCs no estado", ["buscar_imoveis_em_camadas", "buscar_terras_indigenas", "buscar_unidades_conservacao"]),
    ("Verificar fazendas que intersectam camadas estaduais e áreas de preservação", ["buscar_imoveis_em_camadas", "buscar_camadas_estaduais"]),

    # ---- Cruzamento de Passivos Extremos (Queimada + Desmatamento no mesmo Imóvel) ----
    ("Quais propriedades rurais têm passivo de desmatamento e focos de queimada?", ["buscar_passivos_imovel", "buscar_imoveis_desmatamento", "buscar_imoveis_queimada"]),
    ("Buscar CAR de fazendas com alerta de corte raso e incêndio ao mesmo tempo", ["buscar_imoveis_desmatamento", "buscar_imoveis_queimada"]),
]