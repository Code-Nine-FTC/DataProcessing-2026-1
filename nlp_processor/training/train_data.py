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
    ("Quantos focos de queimada no município de São Paulo?", ["buscar_queimadas"]),
    ("Quantos focos de queimada foram detectados em Campinas?", ["buscar_queimadas"]),
    ("Número de focos de incêndio em Guarulhos", ["buscar_queimadas"]),
    ("Quero saber quantas queimadas ocorreram em Santo André", ["buscar_queimadas"]),
    ("Total de focos de calor registrados em Osasco", ["buscar_queimadas"]),
    ("Focos de queimada detectados em Santos no último mês", ["buscar_queimadas"]),
    ("Quantas queimadas houve em São Bernardo do Campo?", ["buscar_queimadas"]),
    ("Mostra só os focos de incêndio em Jundiaí", ["buscar_queimadas"]),
    ("Apenas queimadas em Marília, sem desmatamento", ["buscar_queimadas"]),
    ("Focos de fogo no município de São Paulo em 2024", ["buscar_queimadas"]),

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
    ("Quantos alertas de desmatamento no município de São Paulo?", ["buscar_desmatamentos"]),
    ("Quantos alertas PRODES foram registrados em Campinas?", ["buscar_desmatamentos"]),
    ("Mostra apenas o desmatamento em Guarulhos", ["buscar_desmatamentos"]),
    ("Alertas de supressão vegetal detectados em Jundiaí", ["buscar_desmatamentos"]),
    ("Quero saber só sobre desmatamento em Ribeirão Preto", ["buscar_desmatamentos"]),
    ("Total de alertas de corte raso em São José dos Campos", ["buscar_desmatamentos"]),
    ("Quantas áreas foram desmatadas em Piracicaba?", ["buscar_desmatamentos"]),
    ("Alertas de perda de vegetação nativa em Bauru", ["buscar_desmatamentos"]),
    ("Desmatamento detectado pelo PRODES Mata Atlântica em São Paulo", ["buscar_desmatamentos"]),

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
    ("Imóveis rurais que tiveram focos de queimada dentro da propriedade em Campinas", ["buscar_imoveis_queimada"]),
    ("Quais fazendas em Sorocaba tiveram fogo registrado dentro do CAR?", ["buscar_imoveis_queimada"]),
    ("Propriedades rurais afetadas por queimadas em São José dos Campos", ["buscar_imoveis_queimada"]),
    ("Listar CARs com histórico de incêndio dentro do perímetro em SP", ["buscar_imoveis_queimada"]),
    ("Quais imóveis do SICAR registraram queimadas em seus limites?", ["buscar_imoveis_queimada"]),
    ("Fazendas com focos de calor dentro da propriedade em Bauru", ["buscar_imoveis_queimada"]),
    ("Imóveis rurais com queimadas registradas dentro do polígono do CAR em Marília", ["buscar_imoveis_queimada"]),
    ("Quais propriedades em Presidente Prudente tiveram incêndio no interior?", ["buscar_imoveis_queimada"]),
    ("CAR de imóveis rurais atingidos internamente por fogo no estado de SP", ["buscar_imoveis_queimada"]),

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
    ("Quais fazendas estão dentro de terras indígenas no estado de SP?", ["buscar_imoveis_ti"]),
    ("CARs sobrepostos a demarcações indígenas em São Paulo", ["buscar_imoveis_ti"]),
    ("Imóveis rurais com sobreposição em TIs paulistas", ["buscar_imoveis_ti"]),
    ("Listar propriedades rurais dentro de reservas indígenas em SP", ["buscar_imoveis_ti"]),
    ("Quais cadastros do CAR conflitam com terras indígenas homologadas?", ["buscar_imoveis_ti"]),
    ("Fazendas com conflito fundiário em terras indígenas no Vale do Ribeira", ["buscar_imoveis_ti"]),
    ("Imóvel rural dentro de terra indígena demarcada em SP", ["buscar_imoveis_ti"]),
    ("Propriedades do SICAR que invadem TIs no litoral paulista", ["buscar_imoveis_ti"]),
    ("Percentual de sobreposição de imóveis rurais com terras indígenas em SP", ["buscar_imoveis_ti"]),
    ("Buscar CAR com intersecção em territórios indígenas guarani em São Paulo", ["buscar_imoveis_ti"]),

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
    ("Quais leis regulamentam a queima de vegetação nativa em SP?", ["buscar_documentos"]),
    ("O que é o Programa de Regularização Ambiental do estado?", ["buscar_documentos"]),
    ("Qual a legislação sobre áreas de preservação permanente no Brasil?", ["buscar_documentos"]),
    ("Documentos sobre o PRODES e sua metodologia de detecção de desmatamento", ["buscar_documentos"]),
    ("Normativas do IBAMA para o monitoramento de queimadas e incêndios", ["buscar_documentos"]),
    ("Como funciona o CAR e o SICAR no estado de São Paulo?", ["buscar_documentos"]),
    ("Qual a resolução CONAMA sobre desmatamento em Mata Atlântica?", ["buscar_documentos"]),
    ("Legislação federal sobre proteção de terras indígenas", ["buscar_documentos"]),
    ("Quais são os critérios para homologação de territórios quilombolas?", ["buscar_documentos"]),
    ("Resolução SMA sobre unidades de conservação estaduais em SP", ["buscar_documentos"]),
    ("Manual de uso do DETER para monitoramento ambiental", ["buscar_documentos"]),
    ("O que é o Código Florestal Brasileiro e como ele se aplica em SP?", ["buscar_documentos"]),
    ("Qual a lei que protege as APPs em margens de rios no estado?", ["buscar_documentos"]),
    ("Quais são as normas para regularização fundiária em terras indígenas?", ["buscar_documentos"]),
    ("Como funciona o programa BDQueimadas do INPE?", ["buscar_documentos"]),
    ("Quais resoluções regulamentam as unidades de conservação em SP?", ["buscar_documentos"]),
    ("Explique como o SNUC classifica as unidades de conservação", ["buscar_documentos"]),
    ("Quais são as penalidades para desmatamento ilegal na Mata Atlântica?", ["buscar_documentos"]),
    ("Documentação sobre o cadastramento de imóveis no SICAR", ["buscar_documentos"]),
    ("O que diz a lei da Mata Atlântica sobre supressão de vegetação?", ["buscar_documentos"]),
    ("Como é feita a demarcação de territórios quilombolas pelo INCRA?", ["buscar_documentos"]),
    ("Quais instrumentos legais protegem as terras indígenas no Brasil?", ["buscar_documentos"]),
    ("Normativa sobre reserva legal em imóveis rurais no estado de SP", ["buscar_documentos"]),
    ("Quais são as regras do zoneamento agroambiental paulista?", ["buscar_documentos"]),
    ("Explique a metodologia do PRODES para detecção de desmatamento", ["buscar_documentos"]),
    ("Qual legislação define as zonas de amortecimento de parques estaduais?", ["buscar_documentos"]),

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
    ("territórios quilombolas no Pará", ["fora_escopo"]),
    ("terras indígenas na Amazônia", ["fora_escopo"]),
    ("quilombos no estado do Maranhão", ["fora_escopo"]),
    ("queimadas no Pantanal do Mato Grosso do Sul", ["fora_escopo"]),
    ("desmatamento na Amazônia Legal em 2024", ["fora_escopo"]),
    ("unidades de conservação no Mato Grosso", ["fora_escopo"]),
    ("focos de incêndio no Cerrado do Tocantins", ["fora_escopo"]),
    ("terras indígenas guarani no Rio Grande do Sul", ["fora_escopo"]),
    ("assentamentos do INCRA em Minas Gerais", ["fora_escopo"]),
    ("imóveis rurais no CAR do estado do Paraná", ["fora_escopo"]),
    ("alertas DETER na Amazônia Legal", ["fora_escopo"]),
    ("quilombolas reconhecidos na Bahia pelo INCRA", ["fora_escopo"]),

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
    ("Queimadas dentro da minha propriedade rural SP-3500709-ABCDEF1234567890?", ["buscar_focos_queimada_imovel"]),
    ("Incêndios detectados dentro do imóvel rural SP-3550308-999888777666555444", ["buscar_focos_queimada_imovel"]),
    ("Quais focos de fogo ocorreram dentro do CAR SP-3549904-AAABBBCCC em 2023?", ["buscar_focos_queimada_imovel"]),
    ("Ver queimadas dentro da fazenda com código CAR SP-3548708-XYZ12345", ["buscar_focos_queimada_imovel"]),
    ("Fogo registrado pelo satélite dentro da propriedade CAR SP-3503208-ABC", ["buscar_focos_queimada_imovel"]),
    ("Meu imóvel rural SP000111222 teve algum foco de incêndio?", ["buscar_focos_queimada_imovel"]),
    ("Focos de queimada nos últimos 12 meses dentro do CAR SP555666777", ["buscar_focos_queimada_imovel"]),
    ("Histórico de fogo dentro da propriedade cadastrada como SP333444555", ["buscar_focos_queimada_imovel"]),
    ("Quantos focos de calor foram detectados na fazenda SP-3500105-HASH2024?", ["buscar_focos_queimada_imovel"]),
    ("Quero saber se houve queimada na minha propriedade SP888777666 este ano", ["buscar_focos_queimada_imovel"]),

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
    ("Quais imóveis do CAR estão em áreas protegidas ou territórios quilombolas?", ["buscar_imoveis_em_camadas", "buscar_imoveis_quilombo"]),
    ("Sobreposição de propriedades rurais com TIs e UCs no estado", ["buscar_imoveis_ti", "buscar_imoveis_em_camadas"]),
    ("Verificar fazendas que intersectam camadas estaduais e áreas de preservação", ["buscar_imoveis_em_camadas", "buscar_camadas_estaduais"]),

    ("Quais propriedades rurais têm passivo de desmatamento e focos de queimada?", ["buscar_imoveis_desmatamento", "buscar_imoveis_queimada"]),
    ("Buscar CAR de fazendas com alerta de corte raso e incêndio ao mesmo tempo", ["buscar_imoveis_desmatamento", "buscar_imoveis_queimada"]),
    ("Quais fazendas têm tanto desmatamento quanto queimada registrados?", ["buscar_imoveis_desmatamento", "buscar_imoveis_queimada"]),

    # =========================================================================
    # ---- EXPANSÃO: RELAÇÕES DO BANCO (RelImovelTI, RelImovelQuilombo,
    #      RelImovelUC, RelImovelBacia, RelImovelQueimada, RelImovelDesmatamento)
    # =========================================================================

    # ---- buscar_imoveis_ti: RelImovelTI ----
    ("Imóveis rurais cadastrados no CAR que sobrepõem terras indígenas", ["buscar_imoveis_ti"]),
    ("Fazendas do SICAR dentro do perímetro de TIs homologadas", ["buscar_imoveis_ti"]),
    ("Quais cadastros CAR cruzam com demarcações indígenas no estado?", ["buscar_imoveis_ti"]),
    ("Propriedades rurais com conflito fundiário em terra indígena SP", ["buscar_imoveis_ti"]),
    ("Imóvel rural dentro da TI Jaraguá", ["buscar_imoveis_ti"]),
    ("Listar CARs sobrepostos a territórios indígenas guarani", ["buscar_imoveis_ti"]),

    # ---- buscar_imoveis_quilombo: RelImovelQuilombo ----
    ("Propriedades rurais que invadem territórios quilombolas no Vale do Ribeira", ["buscar_imoveis_quilombo"]),
    ("Imóveis do CAR com sobreposição em comunidades quilombolas", ["buscar_imoveis_quilombo"]),
    ("Fazendas privadas que cruzam com áreas de quilombo em Eldorado", ["buscar_imoveis_quilombo"]),
    ("Quais cadastros SICAR intersectam territórios quilombolas reconhecidos?", ["buscar_imoveis_quilombo"]),
    ("Conflito fundiário entre imóveis rurais e quilombos em SP", ["buscar_imoveis_quilombo"]),
    ("Listar propriedades sobrepostas a quilombos no litoral paulista", ["buscar_imoveis_quilombo"]),

    # ---- buscar_imoveis_em_camadas: RelImovelUC e camadas estaduais ----
    ("Imóveis rurais dentro do perímetro de unidades de conservação", ["buscar_imoveis_em_camadas"]),
    ("Fazendas do CAR sobrepostas a parques estaduais em SP", ["buscar_imoveis_em_camadas"]),
    ("Propriedades rurais na faixa de amortecimento de APAs", ["buscar_imoveis_em_camadas"]),
    ("Quais CARs estão em áreas de vulnerabilidade ambiental estadual?", ["buscar_imoveis_em_camadas"]),
    ("Imóveis cadastrados dentro de zonas de restrição hídrica do DataGeo", ["buscar_imoveis_em_camadas"]),

    # ---- buscar_camadas_estaduais: inclui BaciaHidrografica ----
    ("Mostrar o mapa de bacias hidrográficas do estado de São Paulo", ["buscar_camadas_estaduais"]),
    ("Quais são as bacias hidrográficas da Região Administrativa de Campinas?", ["buscar_camadas_estaduais"]),
    ("Camadas de uso e cobertura do solo disponíveis no DataGeo SP", ["buscar_camadas_estaduais"]),
    ("Zoneamento ecológico-econômico do estado de São Paulo", ["buscar_camadas_estaduais"]),
    ("Mapa de APPs e reservas legais das bacias paulistas", ["buscar_camadas_estaduais"]),

    # ---- buscar_imoveis_queimada: exemplos contrastivos (SEM buscar_queimadas) ----
    ("Listar imóveis rurais com foco de calor dentro dos limites da propriedade", ["buscar_imoveis_queimada"]),
    ("Fazendas que registraram incêndio dentro do perímetro cadastrado no CAR", ["buscar_imoveis_queimada"]),
    ("Propriedades atingidas por queimada dentro da área do imóvel", ["buscar_imoveis_queimada"]),
    ("Quais CARs tiveram fogo detectado dentro do polígono?", ["buscar_imoveis_queimada"]),
    ("Imóveis rurais com cicatriz de queimada dentro do cadastro", ["buscar_imoveis_queimada"]),

    # ---- buscar_imoveis_desmatamento: exemplos contrastivos (SEM buscar_desmatamentos) ----
    ("Fazendas com alerta de supressão vegetal dentro do perímetro do CAR", ["buscar_imoveis_desmatamento"]),
    ("Quais imóveis têm desmatamento detectado dentro dos limites da propriedade?", ["buscar_imoveis_desmatamento"]),
    ("Propriedades rurais com corte raso dentro do polígono cadastrado", ["buscar_imoveis_desmatamento"]),
    ("Imóveis com PRODES ou DETER dentro do perímetro em Bauru", ["buscar_imoveis_desmatamento"]),
    ("Quais imóveis rurais têm alertas PRODES dentro do polígono?", ["buscar_imoveis_desmatamento"]),
    ("Fazendas em Botucatu com corte raso detectado pelo DETER dentro do imóvel", ["buscar_imoveis_desmatamento"]),
    ("CAR de propriedades com supressão vegetal dentro dos limites em Marília", ["buscar_imoveis_desmatamento"]),
    ("Imóveis rurais em Sorocaba com desmatamento detectado dentro do cadastro", ["buscar_imoveis_desmatamento"]),
    ("Listar CARs com alertas de corte raso dentro do polígono registrado", ["buscar_imoveis_desmatamento"]),
    ("Propriedades rurais com vegetação nativa removida dentro da área do imóvel", ["buscar_imoveis_desmatamento"]),
    ("Fazendas que possuem alerta de supressão dentro do perímetro em Campinas", ["buscar_imoveis_desmatamento"]),
    ("Imóveis do SICAR com detecção de corte de vegetação internamente", ["buscar_imoveis_desmatamento"]),

    # ---- buscar_maiores_quantidades: rankings com base nas relações do banco ----
    ("Qual município tem mais imóveis rurais com focos de queimada dentro?", ["buscar_maiores_quantidades"]),
    ("Top 5 cidades com maior área de imóveis sobrepostos a desmatamento", ["buscar_maiores_quantidades"]),
    ("Quais municípios concentram mais conflitos entre CARs e terras indígenas?", ["buscar_maiores_quantidades"]),
    ("Ranking de municípios com mais imóveis sobrepostos a quilombos", ["buscar_maiores_quantidades"]),
    ("Quais RAs têm mais imóveis dentro de unidades de conservação?", ["buscar_maiores_quantidades"]),
    ("Municípios com maior quantidade de propriedades em camadas ambientais estaduais", ["buscar_maiores_quantidades"]),

    # =========================================================================
    # ---- MULTI-INTENTS: COBERTURA DAS RELAÇÕES DO BANCO ----
    # =========================================================================

    # ---- RelImovelQueimada: focos + imóveis afetados ----
    ("Focos de queimada em Campinas e quais imóveis rurais foram atingidos", ["buscar_queimadas", "buscar_imoveis_queimada"]),
    ("Mapa de incêndios e fazendas afetadas na RA de Sorocaba", ["buscar_queimadas", "buscar_imoveis_queimada"]),
    ("Queimadas registradas e propriedades com foco dentro em Botucatu", ["buscar_queimadas", "buscar_imoveis_queimada"]),

    # ---- RelImovelDesmatamento: alertas + imóveis afetados ----
    ("Alertas de desmatamento e fazendas com sobreposição em Marília", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("PRODES e imóveis rurais sobrepostos a corte raso em SP", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Corte de vegetação detectado e propriedades afetadas em Presidente Prudente", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),

    # ---- RelImovelTI: terras indígenas + imóveis sobrepostos ----
    ("Mapa de terras indígenas em SP e os imóveis rurais que as sobrepõem", ["buscar_terras_indigenas", "buscar_imoveis_ti"]),
    ("TIs homologadas e fazendas com conflito fundiário no estado", ["buscar_terras_indigenas", "buscar_imoveis_ti"]),
    ("Territórios indígenas e cadastros CAR que invadem suas áreas", ["buscar_terras_indigenas", "buscar_imoveis_ti"]),

    # ---- RelImovelQuilombo: quilombolas + imóveis sobrepostos ----
    ("Territórios quilombolas no Vale do Ribeira e propriedades rurais sobrepostas", ["buscar_quilombolas", "buscar_imoveis_quilombo"]),
    ("Comunidades quilombolas e imóveis do CAR que cruzam com elas", ["buscar_quilombolas", "buscar_imoveis_quilombo"]),
    ("Quilombos reconhecidos e conflitos com fazendas cadastradas no SICAR", ["buscar_quilombolas", "buscar_imoveis_quilombo"]),

    # ---- RelImovelUC: unidades de conservação + imóveis sobrepostos ----
    ("Parques estaduais e fazendas do CAR dentro do perímetro", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Unidades de conservação e imóveis rurais sobrepostos em SP", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("APAs e propriedades cadastradas dentro dos limites de proteção", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),

    # ---- RelImovelBacia via camadas: bacias hidrográficas + imóveis ----
    ("Bacias hidrográficas de SP e fazendas localizadas dentro delas", ["buscar_camadas_estaduais", "buscar_imoveis_em_camadas"]),
    ("Imóveis rurais nas margens de bacias hidrográficas e camadas de restrição", ["buscar_camadas_estaduais", "buscar_imoveis_em_camadas"]),

    # ---- Cruzamentos 3 camadas: TI + Quilombo + Imóvel ----
    ("Imóveis rurais que sobrepõem tanto terras indígenas quanto quilombolas", ["buscar_imoveis_ti", "buscar_imoveis_quilombo"]),
    ("Fazendas em conflito com TIs e territórios quilombolas no estado", ["buscar_imoveis_ti", "buscar_imoveis_quilombo"]),

    # ---- Cruzamentos 3 camadas: Queimada + Desmatamento + TI ----
    ("Focos de fogo e corte de vegetação em terras indígenas em SP", ["buscar_queimadas", "buscar_desmatamentos", "buscar_terras_indigenas"]),
    ("Monitorar queimadas e desmatamento dentro de territórios indígenas", ["buscar_queimadas", "buscar_desmatamentos", "buscar_terras_indigenas"]),

    # ---- Cruzamentos 3 camadas: Desmatamento + UC + Imóvel ----
    ("Alertas de supressão vegetal em UCs e imóveis sobrepostos às áreas protegidas", ["buscar_desmatamentos", "buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Desmatamento dentro de parques estaduais e fazendas cadastradas no entorno", ["buscar_desmatamentos", "buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),

    # =========================================================================
    # ---- EXPANSÃO: NOVOS FILTROS DE ENTIDADE (tipo_alerta, esfera_uc, bioma) ----
    # =========================================================================

    # ---- buscar_desmatamentos com tipo_alerta (PRODES / DETER) ----
    ("Alertas PRODES de desmatamento no município de Campinas", ["buscar_desmatamentos"]),
    ("Quero ver os dados do PRODES Mata Atlântica para São Paulo", ["buscar_desmatamentos"]),
    ("Alertas do DETER para monitoramento de corte raso em SP", ["buscar_desmatamentos"]),
    ("Desmatamento detectado pelo PRODES Cerrado em Bauru", ["buscar_desmatamentos"]),
    ("Alertas DETER de supressão vegetal em São José dos Campos", ["buscar_desmatamentos"]),
    ("PRODES Mata Atlântica: alertas no município de Santos", ["buscar_desmatamentos"]),
    ("Dados do PRODES e DETER combinados para o Vale do Ribeira", ["buscar_desmatamentos"]),

    # ---- buscar_unidades_conservacao com esfera (Federal / Estadual / Municipal) ----
    ("Parques nacionais localizados no litoral paulista", ["buscar_unidades_conservacao"]),
    ("Unidades de conservação federais no estado de São Paulo", ["buscar_unidades_conservacao"]),
    ("APAs estaduais no Vale do Ribeira em SP", ["buscar_unidades_conservacao"]),
    ("Quais são as reservas biológicas federais em SP?", ["buscar_unidades_conservacao"]),
    ("Parques estaduais administrados pelo Instituto Florestal", ["buscar_unidades_conservacao"]),
    ("Unidades de conservação municipais no município de São Paulo", ["buscar_unidades_conservacao"]),
    ("Florestas nacionais e estações ecológicas federais em SP", ["buscar_unidades_conservacao"]),

    # ---- buscar_queimadas com bioma (Mata Atlântica / Cerrado) ----
    ("Focos de queimada registrados na Mata Atlântica paulista", ["buscar_queimadas"]),
    ("Incêndios no Cerrado do estado de São Paulo", ["buscar_queimadas"]),
    ("Queimadas ocorridas em áreas de Mata Atlântica em SP em 2026", ["buscar_queimadas"]),
    ("Focos de calor no Cerrado paulista detectados pelo INPE", ["buscar_queimadas"]),
    ("Histórico de incêndios na Mata Atlântica de Sorocaba", ["buscar_queimadas"]),

    # =========================================================================
    # ---- EXPANSÃO: MAIS EXEMPLOS PARA INTENÇÕES COM POUCOS DADOS ----
    # =========================================================================

    # ---- buscar_assentamentos (expansão) ----
    ("Assentamentos rurais do INCRA no Pontal do Paranapanema", ["buscar_assentamentos"]),
    ("Projetos de assentamento estaduais do ITESP em SP", ["buscar_assentamentos"]),
    ("Quais são as áreas de reforma agrária em Presidente Prudente?", ["buscar_assentamentos"]),
    ("Assentamentos rurais próximos de Andradina", ["buscar_assentamentos"]),
    ("Mapa dos assentamentos do INCRA no estado de São Paulo", ["buscar_assentamentos"]),

    # ---- buscar_quilombolas (expansão) ----
    ("Territórios quilombolas reconhecidos no Vale do Ribeira SP", ["buscar_quilombolas"]),
    ("Comunidades quilombolas certificadas pela FCP em São Paulo", ["buscar_quilombolas"]),
    ("Quilombos titulados pelo INCRA no estado de SP", ["buscar_quilombolas"]),
    ("Onde ficam os territórios quilombolas no litoral sul paulista?", ["buscar_quilombolas"]),
    ("Áreas de comunidade tradicional de quilombo em Registro", ["buscar_quilombolas"]),

    # ---- buscar_imoveis_rurais (expansão) ----
    ("Imóveis rurais cadastrados no SICAR em São José do Rio Preto", ["buscar_imoveis_rurais"]),
    ("Propriedades rurais com situação ativa no CAR em Araraquara", ["buscar_imoveis_rurais"]),
    ("Quais fazendas estão cadastradas no CAR em Araçatuba?", ["buscar_imoveis_rurais"]),
    ("Dados de CAR de propriedades rurais em Presidente Prudente", ["buscar_imoveis_rurais"]),
    ("Imóveis rurais registrados em Botucatu com situação ativa", ["buscar_imoveis_rurais"]),
    ("Mapa de polígonos de imóveis rurais em Franca no SICAR", ["buscar_imoveis_rurais"]),

    # ---- buscar_camadas_estaduais (expansão) ----
    ("Mapa de vulnerabilidade ambiental do DataGeo SP", ["buscar_camadas_estaduais"]),
    ("Camadas de uso e cobertura do solo do estado de São Paulo", ["buscar_camadas_estaduais"]),
    ("Zoneamento agroambiental do estado de São Paulo", ["buscar_camadas_estaduais"]),
    ("Camada geomorfológica disponível na plataforma DataGeo", ["buscar_camadas_estaduais"]),
    ("Mapa de solos e aptidão agrícola do estado de SP", ["buscar_camadas_estaduais"]),

    # ---- buscar_imoveis_em_camadas (expansão) ----
    ("Fazendas do CAR localizadas em zonas de restrição hídrica em SP", ["buscar_imoveis_em_camadas"]),
    ("Quais imóveis rurais estão em áreas de vulnerabilidade ambiental estadual?", ["buscar_imoveis_em_camadas"]),
    ("Propriedades rurais dentro de zonas de amortecimento de reservas biológicas", ["buscar_imoveis_em_camadas"]),
    ("CARs sobrepostos a camadas de restrição do DataGeo", ["buscar_imoveis_em_camadas"]),
    ("Imóveis rurais em áreas de proteção de mananciais estaduais", ["buscar_imoveis_em_camadas"]),

    # ---- buscar_passivos_imovel (expansão + formato real CAR) ----
    ("Verificar passivos ambientais e embargos do imóvel SP000123456", ["buscar_passivos_imovel"]),
    ("Relatório de sobreposições ambientais para a propriedade CAR SP999888777", ["buscar_passivos_imovel"]),
    ("O imóvel rural SP111222333 tem algum passivo de desmatamento ou TI?", ["buscar_passivos_imovel"]),
    ("Quais áreas protegidas se sobrepõem ao imóvel SP555444333?", ["buscar_passivos_imovel"]),
    ("Quais passivos ambientais existem no imóvel rural com código CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", ["buscar_passivos_imovel"]),
    ("Verificar passivos e embargos do CAR SP-3550308-12AB34CD56EF78901234567890ABCDEF", ["buscar_passivos_imovel"]),
    ("O imóvel CAR SP-3500105-ABCDEF1234567890ABCDEF1234567890 tem sobreposição com TI ou UC?", ["buscar_passivos_imovel"]),

    # ---- buscar_focos_queimada_imovel (formato real CAR) ----
    ("Houve focos de queimada dentro do imóvel SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", ["buscar_focos_queimada_imovel"]),
    ("Incêndios detectados pelo satélite no CAR SP-3550308-12AB34CD56EF78901234567890ABCDEF", ["buscar_focos_queimada_imovel"]),

    # ---- buscar_imoveis_rurais (formato real CAR) ----
    ("Mostrar o polígono do imóvel rural SP-3500709-F80A461130164CF9A0B0FEAB5611FA40", ["buscar_imoveis_rurais"]),
    ("Localizar a fazenda com código CAR SP-3550308-12AB34CD56EF78901234567890ABCDEF no mapa", ["buscar_imoveis_rurais"]),

    # ---- buscar_terras_indigenas (expansão) ----
    ("Terras indígenas homologadas no estado de São Paulo", ["buscar_terras_indigenas"]),
    ("TIs declaradas ou em processo de demarcação em SP", ["buscar_terras_indigenas"]),
    ("Localização da Terra Indígena Jaraguá em São Paulo", ["buscar_terras_indigenas"]),
    ("Territórios indígenas guarani no litoral paulista", ["buscar_terras_indigenas"]),
    ("Quais são as TIs na região de Peruíbe?", ["buscar_terras_indigenas"]),

    # ---- buscar_unidades_conservacao (expansão) ----
    ("Quais são as RPPNs cadastradas no estado de SP?", ["buscar_unidades_conservacao"]),
    ("Estações ecológicas e reservas biológicas em São Paulo", ["buscar_unidades_conservacao"]),
    ("Mapa das APAs do litoral norte paulista", ["buscar_unidades_conservacao"]),
    ("Reservas extrativistas no Vale do Ribeira", ["buscar_unidades_conservacao"]),
    ("Quais parques estaduais existem em Campinas?", ["buscar_unidades_conservacao"]),

    # ---- buscar_maiores_quantidades (expansão) ----
    ("Quais municípios têm mais alertas PRODES em SP?", ["buscar_maiores_quantidades"]),
    ("Top 10 municípios com mais focos de queimada no estado", ["buscar_maiores_quantidades"]),
    ("Quais são as RAs com maior número de terras indígenas?", ["buscar_maiores_quantidades"]),
    ("Municípios com mais territórios quilombolas em SP", ["buscar_maiores_quantidades"]),
    ("Ranking de municípios com mais unidades de conservação em SP", ["buscar_maiores_quantidades"]),

    # =========================================================================
    # ---- MULTI-INTENT: COMBINAÇÕES COM NOVAS ENTIDADES ----
    # =========================================================================

    # ---- PRODES + imóveis ----
    ("Alertas PRODES Mata Atlântica e propriedades rurais sobrepostas em SP", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("DETER detectou corte raso: quais fazendas foram afetadas em Marília?", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Quais imóveis rurais foram afetados por desmatamento PRODES Cerrado em SP?", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Alertas DETER e propriedades rurais com sobreposição em Sorocaba", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Corte raso detectado pelo PRODES: quais CARs estão sobrepostos em Bauru?", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Quais fazendas em Presidente Prudente estão dentro de alertas de desmatamento?", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Imóveis rurais com sobreposição a alertas PRODES Mata Atlântica no Vale do Paraíba", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Desmatamento detectado pelo DETER e propriedades rurais afetadas em Ribeirão Preto", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Listar fazendas que coincidem com alertas de supressão vegetal em SP", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),
    ("Alertas de perda florestal e CARs sobrepostos no Pontal do Paranapanema", ["buscar_desmatamentos", "buscar_imoveis_desmatamento"]),

    # ---- UCs estaduais + imóveis ----
    ("Parques estaduais e imóveis rurais dentro de seus limites", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Reservas biológicas estaduais e propriedades com sobreposição em SP", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Quais imóveis rurais estão dentro de APAs no estado de São Paulo?", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Propriedades rurais sobrepostas a parques nacionais e estaduais em SP", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Fazendas com sobreposição em unidades de conservação em Campinas", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Imóveis rurais dentro de estações ecológicas paulistas", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("CARs sobrepostos a RPPNs e reservas biológicas em São Paulo", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Mapa de UCs estaduais e imóveis rurais que as intersectam em SP", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Quais propriedades rurais invadem florestas nacionais ou parques estaduais?", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),
    ("Áreas de proteção ambiental e fazendas cadastradas no SICAR em Ubatuba", ["buscar_unidades_conservacao", "buscar_imoveis_em_camadas"]),

    # ---- Queimadas + TI ----
    ("Incêndios na Mata Atlântica paulista dentro de terras indígenas", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Focos de queimada em terras indígenas no estado de São Paulo", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Quais TIs tiveram focos de incêndio em SP?", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Queimadas registradas dentro de reservas indígenas paulistas", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Focos de calor em áreas indígenas demarcadas em SP", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Incêndios detectados por satélite em terras indígenas homologadas em São Paulo", ["buscar_queimadas", "buscar_terras_indigenas"]),
    ("Mapa de focos de queimada sobrepostos a terras indígenas no litoral paulista", ["buscar_queimadas", "buscar_terras_indigenas"]),

    # ---- Queimadas + Quilombolas ----
    ("Focos de calor no Cerrado de SP em áreas quilombolas", ["buscar_queimadas", "buscar_quilombolas"]),
    ("Queimadas em territórios quilombolas no Vale do Ribeira", ["buscar_queimadas", "buscar_quilombolas"]),
    ("Incêndios registrados dentro de comunidades quilombolas em SP", ["buscar_queimadas", "buscar_quilombolas"]),
    ("Focos de queimada sobrepostos a territórios quilombolas em São Paulo", ["buscar_queimadas", "buscar_quilombolas"]),
    ("Quais quilombos tiveram focos de incêndio em São Paulo?", ["buscar_queimadas", "buscar_quilombolas"]),
    ("Calor e incêndios em comunidades tradicionais quilombolas paulistas", ["buscar_queimadas", "buscar_quilombolas"]),

    # ---- Desmatamento + TI ----
    ("Alertas de desmatamento dentro de terras indígenas em SP", ["buscar_desmatamentos", "buscar_terras_indigenas"]),
    ("Supressão de vegetação em TIs paulistas detectada pelo PRODES", ["buscar_desmatamentos", "buscar_terras_indigenas"]),
    ("Corte raso em terras indígenas homologadas no estado de São Paulo", ["buscar_desmatamentos", "buscar_terras_indigenas"]),
    ("Quais terras indígenas tiveram alertas DETER em SP?", ["buscar_desmatamentos", "buscar_terras_indigenas"]),

    # ---- Desmatamento + Quilombolas ----
    ("Desmatamento em territórios quilombolas no estado de SP", ["buscar_desmatamentos", "buscar_quilombolas"]),
    ("Alertas de perda de vegetação em comunidades quilombolas paulistas", ["buscar_desmatamentos", "buscar_quilombolas"]),
    ("Supressão vegetal detectada em quilombos do Vale do Ribeira", ["buscar_desmatamentos", "buscar_quilombolas"]),

    # ---- Queimadas + imóveis ----
    ("Focos de queimada e propriedades rurais afetadas em Campinas", ["buscar_queimadas", "buscar_imoveis_queimada"]),
    ("Quais fazendas tiveram focos de incêndio dentro da propriedade em SP?", ["buscar_queimadas", "buscar_imoveis_queimada"]),
    ("Imóveis rurais com queimadas dentro do CAR em Sorocaba", ["buscar_queimadas", "buscar_imoveis_queimada"]),
    ("Propriedades rurais afetadas por focos de calor em São José dos Campos", ["buscar_queimadas", "buscar_imoveis_queimada"]),

    # ---- Ranking + TI + UC ----
    ("Quais municípios concentram mais TIs e UCs sobrepostas em SP?", ["buscar_maiores_quantidades", "buscar_terras_indigenas", "buscar_unidades_conservacao"]),
    ("Ranking de municípios com maior sobreposição entre terras indígenas e unidades de conservação em SP", ["buscar_maiores_quantidades", "buscar_terras_indigenas", "buscar_unidades_conservacao"]),
    ("Quais cidades paulistas têm mais TIs e áreas protegidas combinadas?", ["buscar_maiores_quantidades", "buscar_terras_indigenas", "buscar_unidades_conservacao"]),
    ("Top municípios em SP com maior concentração de TIs homologadas e UCs federais", ["buscar_maiores_quantidades", "buscar_terras_indigenas", "buscar_unidades_conservacao"]),

    # ---- Ranking + queimadas ----
    ("Ranking dos municípios com mais focos de queimada em São Paulo", ["buscar_maiores_quantidades", "buscar_queimadas"]),
    ("Top 5 cidades paulistas com maior número de incêndios registrados", ["buscar_maiores_quantidades", "buscar_queimadas"]),
    ("Quais os municípios que mais registraram focos de calor no estado?", ["buscar_maiores_quantidades", "buscar_queimadas"]),

    # ---- Ranking + desmatamento ----
    ("Ranking dos municípios com mais alertas de desmatamento em SP", ["buscar_maiores_quantidades", "buscar_desmatamentos"]),
    ("Top cidades com maior área desmatada no estado de São Paulo", ["buscar_maiores_quantidades", "buscar_desmatamentos"]),
    ("Quais municípios lideram o desmatamento em São Paulo?", ["buscar_maiores_quantidades", "buscar_desmatamentos"]),

    # ---- buscar_maiores_quantidades: "qual município teve o maior X" — queimadas ----
    ("qual o município que teve o maior foco de queimada?", ["buscar_maiores_quantidades"]),
    ("qual o município do estado de sp que teve o maior foco de queimada?", ["buscar_maiores_quantidades"]),
    ("qual município teve o maior número de focos de queimada?", ["buscar_maiores_quantidades"]),
    ("qual cidade registrou mais focos de incêndio em SP?", ["buscar_maiores_quantidades"]),
    ("qual é o município com mais queimadas no estado de São Paulo?", ["buscar_maiores_quantidades"]),
    ("qual município de SP teve mais focos de queimada?", ["buscar_maiores_quantidades"]),
    ("qual foi o município com maior incidência de queimadas?", ["buscar_maiores_quantidades"]),
    ("qual o município paulista com mais focos de calor registrados?", ["buscar_maiores_quantidades"]),
    ("quero saber qual município teve o maior índice de queimadas", ["buscar_maiores_quantidades"]),
    ("qual cidade do estado de SP teve mais queimadas?", ["buscar_maiores_quantidades"]),
    ("qual município concentrou o maior número de incêndios?", ["buscar_maiores_quantidades"]),
    ("qual município do estado registrou mais queimadas recentemente?", ["buscar_maiores_quantidades"]),
    ("qual cidade paulista teve o maior registro de focos de fogo?", ["buscar_maiores_quantidades"]),
    ("me diga qual município de SP teve mais focos de calor", ["buscar_maiores_quantidades"]),

    # ---- buscar_maiores_quantidades: "qual município teve o maior X" — desmatamento ----
    ("qual o município com mais desmatamento no estado de SP?", ["buscar_maiores_quantidades"]),
    ("qual cidade teve mais alertas de desmatamento em São Paulo?", ["buscar_maiores_quantidades"]),
    ("qual município do estado de São Paulo registrou mais desmatamento?", ["buscar_maiores_quantidades"]),
    ("qual é a cidade com maior área desmatada em SP?", ["buscar_maiores_quantidades"]),
    ("qual município paulista teve o maior número de alertas PRODES?", ["buscar_maiores_quantidades"]),
    ("qual município de SP teve mais supressão de vegetação?", ["buscar_maiores_quantidades"]),
    ("qual cidade do estado concentrou mais alertas de corte raso?", ["buscar_maiores_quantidades"]),

    # ---- buscar_maiores_quantidades: "qual município teve o maior X" — terras indígenas ----
    ("qual o município do estado de sp com mais terras indígenas?", ["buscar_maiores_quantidades"]),
    ("qual cidade de São Paulo concentra mais territórios indígenas?", ["buscar_maiores_quantidades"]),
    ("qual município paulista tem o maior número de TIs homologadas?", ["buscar_maiores_quantidades"]),
    ("qual é o município com mais áreas indígenas em SP?", ["buscar_maiores_quantidades"]),
    ("qual cidade do estado de SP tem mais terras indígenas demarcadas?", ["buscar_maiores_quantidades"]),

    # ---- buscar_maiores_quantidades: "qual município teve o maior X" — unidades de conservação ----
    ("qual o município do estado de sp com mais unidades de conservação?", ["buscar_maiores_quantidades"]),
    ("qual cidade paulista concentra mais áreas protegidas?", ["buscar_maiores_quantidades"]),
    ("qual município de SP tem o maior número de UCs?", ["buscar_maiores_quantidades"]),
    ("qual é o município com mais parques e reservas em São Paulo?", ["buscar_maiores_quantidades"]),
    ("qual cidade do estado tem maior extensão de unidades de conservação?", ["buscar_maiores_quantidades"]),

    # ---- buscar_maiores_quantidades: "qual município teve o maior X" — quilombolas ----
    ("qual o município do estado de sp com mais territórios quilombolas?", ["buscar_maiores_quantidades"]),
    ("qual cidade de São Paulo tem mais comunidades quilombolas?", ["buscar_maiores_quantidades"]),
    ("qual município paulista concentra mais quilombos?", ["buscar_maiores_quantidades"]),
    ("qual é o município com maior número de territórios quilombolas em SP?", ["buscar_maiores_quantidades"]),

    # ---- buscar_maiores_quantidades: "qual município teve o maior X" — imóveis rurais ----
    ("qual o município do estado de sp com mais imóveis rurais cadastrados?", ["buscar_maiores_quantidades"]),
    ("qual cidade paulista tem mais propriedades rurais no CAR?", ["buscar_maiores_quantidades"]),
    ("qual município de SP concentra mais imóveis com CAR ativo?", ["buscar_maiores_quantidades"]),

    # ---- buscar_maiores_quantidades: variações genéricas com "estado de SP/São Paulo" ----
    ("qual o município que mais registrou queimadas no estado de São Paulo?", ["buscar_maiores_quantidades"]),
    ("qual município do estado de São Paulo tem mais ocorrências ambientais?", ["buscar_maiores_quantidades"]),
    ("quero saber qual cidade de SP tem o maior número de focos de queimada", ["buscar_maiores_quantidades"]),
    ("qual o pior município em termos de queimadas no estado paulista?", ["buscar_maiores_quantidades"]),
    ("qual cidade lidera o ranking de queimadas em SP?", ["buscar_maiores_quantidades"]),
    ("qual município lidera o ranking de desmatamento no estado de SP?", ["buscar_maiores_quantidades"]),
]