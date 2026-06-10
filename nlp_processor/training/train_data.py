# -*- coding: utf-8 -*-
"""
Dados de treinamento para o classificador de intenções (single-label).

Cada entrada é (texto_exemplo, intent).
O contexto espacial (dentro de UCs, TIs, quilombolas) é detectado pelo
entity_extractor via regex — não pelo classificador. Por isso perguntas
como "queimadas dentro de UCs" recebem intent "buscar_queimadas".

Para treinar:
    python -m nlp_processor.training.train
"""

TRAIN_DATA: list[tuple[str, str]] = [

    # =========================================================================
    # buscar_queimadas
    # =========================================================================
    ("Quais foram os focos de incêndio em Ribeirão Preto em 2024?", "buscar_queimadas"),
    ("Mostra os focos de queimada no estado de São Paulo", "buscar_queimadas"),
    ("Quantos focos de queimada foram registrados em 2023?", "buscar_queimadas"),
    ("Incêndios florestais em Campinas no último ano", "buscar_queimadas"),
    ("Mapa de focos de calor em São Paulo", "buscar_queimadas"),
    ("Quero ver as queimadas detectadas pelo satélite AQUA", "buscar_queimadas"),
    ("Focos de incêndio em Presidente Prudente", "buscar_queimadas"),
    ("Onde ocorreram queimadas em 2025?", "buscar_queimadas"),
    ("Queimadas registradas entre janeiro e março de 2024", "buscar_queimadas"),
    ("Histórico de incêndios em Sorocaba", "buscar_queimadas"),
    ("Focos de calor detectados pelo VIIRS", "buscar_queimadas"),
    ("Houve queimadas em Bauru recentemente?", "buscar_queimadas"),
    ("Quantos focos de queimada no município de São Paulo?", "buscar_queimadas"),
    ("Número de focos de incêndio em Guarulhos", "buscar_queimadas"),
    ("Total de focos de calor registrados em Osasco", "buscar_queimadas"),
    ("Focos de queimada detectados em Santos no último mês", "buscar_queimadas"),
    ("Quantas queimadas houve em São Bernardo do Campo?", "buscar_queimadas"),
    ("Focos de fogo no município de São Paulo em 2024", "buscar_queimadas"),
    ("Focos de queimada registrados na Mata Atlântica paulista", "buscar_queimadas"),
    ("Incêndios no Cerrado do estado de São Paulo", "buscar_queimadas"),
    ("Focos de calor no Cerrado paulista detectados pelo INPE", "buscar_queimadas"),
    # contexto_espacial detectado por regex — intent continua buscar_queimadas
    ("Focos de incêndio detectados dentro de terras indígenas em SP", "buscar_queimadas"),
    ("Queimadas dentro de reservas indígenas paulistas", "buscar_queimadas"),
    ("Focos de calor em áreas indígenas demarcadas em SP", "buscar_queimadas"),
    ("Mapa de focos de queimada sobrepostos a terras indígenas no litoral paulista", "buscar_queimadas"),
    ("Houve registro de fogo em comunidades quilombolas de Eldorado?", "buscar_queimadas"),
    ("Focos de queimada sobrepostos a territórios quilombolas em São Paulo", "buscar_queimadas"),
    ("Quais quilombos tiveram focos de incêndio em São Paulo?", "buscar_queimadas"),
    ("Queimadas em territórios quilombolas no Vale do Ribeira", "buscar_queimadas"),
    ("Incêndios registrados dentro de comunidades quilombolas em SP", "buscar_queimadas"),
    ("quantas queimadas teve em unidade de conservação do estado de sp?", "buscar_queimadas"),
    ("Focos de queimada dentro de parques estaduais em SP", "buscar_queimadas"),
    ("Queimadas em APAs no litoral paulista", "buscar_queimadas"),
    ("Incêndios florestais em unidades de conservação federais em SP", "buscar_queimadas"),
    ("Focos de calor dentro de UCs no estado de São Paulo", "buscar_queimadas"),
    ("Queimadas dentro de áreas protegidas em Ubatuba", "buscar_queimadas"),
    ("Focos de fogo nas reservas biológicas de SP", "buscar_queimadas"),
    ("Queimadas em assentamentos rurais no Pontal do Paranapanema", "buscar_queimadas"),
    ("Focos de incêndio em áreas de assentamento do INCRA em SP", "buscar_queimadas"),

    # =========================================================================
    # buscar_desmatamentos
    # =========================================================================
    ("Exibir alertas de desmatamento em São José dos Campos", "buscar_desmatamentos"),
    ("Onde houve perda de vegetação nativa em 2024?", "buscar_desmatamentos"),
    ("Alertas do DETER para o município de Sorocaba", "buscar_desmatamentos"),
    ("Quero ver o desmatamento acumulado no estado", "buscar_desmatamentos"),
    ("Dados de supressão de vegetação em 2023", "buscar_desmatamentos"),
    ("Quais áreas foram desmatadas recentemente em Botucatu?", "buscar_desmatamentos"),
    ("Mapa de desmatamento ilegal em São Paulo", "buscar_desmatamentos"),
    ("Corte raso detectado por satélite em Santos", "buscar_desmatamentos"),
    ("Taxa de desmatamento no município de Franca", "buscar_desmatamentos"),
    ("Alertas PRODES de desmatamento no município de Campinas", "buscar_desmatamentos"),
    ("Alertas do DETER para monitoramento de corte raso em SP", "buscar_desmatamentos"),
    ("Desmatamento detectado pelo PRODES Mata Atlântica em São Paulo", "buscar_desmatamentos"),
    # com contexto_espacial
    ("Alertas de desmatamento do DETER dentro de parques estaduais", "buscar_desmatamentos"),
    ("Quais unidades de conservação sofreram supressão de vegetação?", "buscar_desmatamentos"),
    ("Monitoramento de corte ilegal em APAs no litoral paulista", "buscar_desmatamentos"),
    ("Desmatamento dentro de parques nacionais em SP", "buscar_desmatamentos"),
    ("Supressão de vegetação em UCs paulistas detectada pelo PRODES", "buscar_desmatamentos"),
    ("Alertas de desmatamento dentro de terras indígenas em SP", "buscar_desmatamentos"),
    ("Supressão de vegetação em TIs paulistas detectada pelo PRODES", "buscar_desmatamentos"),
    ("Corte raso em terras indígenas homologadas no estado de São Paulo", "buscar_desmatamentos"),
    ("Quais terras indígenas tiveram alertas DETER em SP?", "buscar_desmatamentos"),
    ("Desmatamento em territórios quilombolas no estado de SP", "buscar_desmatamentos"),
    ("Alertas de perda de vegetação em comunidades quilombolas paulistas", "buscar_desmatamentos"),
    ("Supressão vegetal detectada em quilombos do Vale do Ribeira", "buscar_desmatamentos"),

    # =========================================================================
    # buscar_unidades_conservacao
    # =========================================================================
    ("Quais são as unidades de conservação em Ubatuba?", "buscar_unidades_conservacao"),
    ("Mostre os parques estaduais no estado de São Paulo", "buscar_unidades_conservacao"),
    ("Exista alguma APA ou reserva biológica em Jundiaí?", "buscar_unidades_conservacao"),
    ("Mapa das Unidades de Conservação Federais em SP", "buscar_unidades_conservacao"),
    ("Quero ver o perímetro das áreas protegidas em Peruíbe", "buscar_unidades_conservacao"),
    ("Lista de florestas estaduais e estações ecológicas", "buscar_unidades_conservacao"),
    ("Quais RPPNs estão cadastradas em São Francisco Xavier?", "buscar_unidades_conservacao"),
    ("Parques nacionais localizados no litoral paulista", "buscar_unidades_conservacao"),
    ("APAs estaduais no Vale do Ribeira em SP", "buscar_unidades_conservacao"),
    ("Quais são as reservas biológicas federais em SP?", "buscar_unidades_conservacao"),
    ("Unidades de conservação municipais no município de São Paulo", "buscar_unidades_conservacao"),
    ("Florestas nacionais e estações ecológicas federais em SP", "buscar_unidades_conservacao"),
    ("Quais são as RPPNs cadastradas no estado de SP?", "buscar_unidades_conservacao"),
    ("Estações ecológicas e reservas biológicas em São Paulo", "buscar_unidades_conservacao"),
    ("Mapa das APAs do litoral norte paulista", "buscar_unidades_conservacao"),
    ("Reservas extrativistas no Vale do Ribeira", "buscar_unidades_conservacao"),
    ("Quais parques estaduais existem em Campinas?", "buscar_unidades_conservacao"),

    # =========================================================================
    # buscar_terras_indigenas
    # =========================================================================
    ("Localizar terras indígenas no estado de São Paulo", "buscar_terras_indigenas"),
    ("Onde ficam as comunidades guarani em Peruíbe?", "buscar_terras_indigenas"),
    ("Mapa das áreas indígenas homologadas pela FUNAI", "buscar_terras_indigenas"),
    ("Quais são as TIs na região do Vale do Ribeira?", "buscar_terras_indigenas"),
    ("Terras indígenas em processo de demarcação em SP", "buscar_terras_indigenas"),
    ("Buscar reservas indígenas perto de Mongaguá", "buscar_terras_indigenas"),
    ("Terras indígenas homologadas no estado de São Paulo", "buscar_terras_indigenas"),
    ("TIs declaradas ou em processo de demarcação em SP", "buscar_terras_indigenas"),
    ("Localização da Terra Indígena Jaraguá em São Paulo", "buscar_terras_indigenas"),
    ("Territórios indígenas guarani no litoral paulista", "buscar_terras_indigenas"),
    ("Quais são as TIs na região de Peruíbe?", "buscar_terras_indigenas"),

    # =========================================================================
    # buscar_quilombolas
    # =========================================================================
    ("Exibir territórios quilombolas em Eldorado", "buscar_quilombolas"),
    ("Onde ficam as comunidades quilombolas no Vale do Ribeira?", "buscar_quilombolas"),
    ("Mapa de terras de comunidades tradicionais de quilombo em SP", "buscar_quilombolas"),
    ("Quais quilombos já possuem título emitido pelo INCRA?", "buscar_quilombolas"),
    ("Buscar áreas quilombolas reconhecidas em Registro", "buscar_quilombolas"),
    ("Territórios quilombolas reconhecidos no Vale do Ribeira SP", "buscar_quilombolas"),
    ("Comunidades quilombolas certificadas pela FCP em São Paulo", "buscar_quilombolas"),
    ("Quilombos titulados pelo INCRA no estado de SP", "buscar_quilombolas"),
    ("Onde ficam os territórios quilombolas no litoral sul paulista?", "buscar_quilombolas"),

    # =========================================================================
    # buscar_assentamentos
    # =========================================================================
    ("Quais são os assentamentos do INCRA em Promissão?", "buscar_assentamentos"),
    ("Mapa de assentamentos rurais no Pontal do Paranapanema", "buscar_assentamentos"),
    ("Projetos de assentamento estadual cadastrados pelo ITESP", "buscar_assentamentos"),
    ("Onde ficam os assentamentos de reforma agrária em SP?", "buscar_assentamentos"),
    ("Assentamentos rurais do INCRA no Pontal do Paranapanema", "buscar_assentamentos"),
    ("Projetos de assentamento estaduais do ITESP em SP", "buscar_assentamentos"),
    ("Quais são as áreas de reforma agrária em Presidente Prudente?", "buscar_assentamentos"),
    ("Assentamentos rurais próximos de Andradina", "buscar_assentamentos"),
    ("Mapa dos assentamentos do INCRA no estado de São Paulo", "buscar_assentamentos"),

    # =========================================================================
    # buscar_imoveis_rurais
    # =========================================================================
    ("Buscar imóveis rurais cadastrados no CAR em Piracicaba", "buscar_imoveis_rurais"),
    ("Visualizar o perímetro do imóvel rural no SICAR", "buscar_imoveis_rurais"),
    ("Dados de propriedades rurais cadastradas em Marília", "buscar_imoveis_rurais"),
    ("Mapa de cadastros ambientais rurais ativos em Limeira", "buscar_imoveis_rurais"),
    ("Mostrar o polígono do imóvel rural SP-3500709-F80A461130164CF9A0B0FEAB5611FA40", "buscar_imoveis_rurais"),
    ("Localizar a fazenda com código CAR SP-3550308-12AB34CD56EF78901234567890ABCDEF no mapa", "buscar_imoveis_rurais"),
    ("Imóveis rurais cadastrados no SICAR em São José do Rio Preto", "buscar_imoveis_rurais"),
    ("Propriedades rurais com situação ativa no CAR em Araraquara", "buscar_imoveis_rurais"),
    ("Quais fazendas estão cadastradas no CAR em Araçatuba?", "buscar_imoveis_rurais"),
    ("Imóveis rurais registrados em Botucatu com situação ativa", "buscar_imoveis_rurais"),
    ("Mapa de polígonos de imóveis rurais em Franca no SICAR", "buscar_imoveis_rurais"),

    # =========================================================================
    # buscar_imoveis_queimada
    # =========================================================================
    ("Quais imóveis rurais foram atingidos por queimadas em 2024?", "buscar_imoveis_queimada"),
    ("Fazendas em Ribeirão Preto que registraram focos de incêndio", "buscar_imoveis_queimada"),
    ("Imóveis rurais que tiveram focos de queimada dentro da propriedade em Campinas", "buscar_imoveis_queimada"),
    ("Quais fazendas em Sorocaba tiveram fogo registrado dentro do CAR?", "buscar_imoveis_queimada"),
    ("Listar CARs com histórico de incêndio dentro do perímetro em SP", "buscar_imoveis_queimada"),
    ("Quais imóveis do SICAR registraram queimadas em seus limites?", "buscar_imoveis_queimada"),
    ("Fazendas com focos de calor dentro da propriedade em Bauru", "buscar_imoveis_queimada"),
    ("Listar imóveis rurais com foco de calor dentro dos limites da propriedade", "buscar_imoveis_queimada"),
    ("Fazendas que registraram incêndio dentro do perímetro cadastrado no CAR", "buscar_imoveis_queimada"),
    ("Quais CARs tiveram fogo detectado dentro do polígono?", "buscar_imoveis_queimada"),

    # =========================================================================
    # buscar_imoveis_desmatamento
    # =========================================================================
    ("Quais propriedades rurais possuem alertas de desmatamento?", "buscar_imoveis_desmatamento"),
    ("Imóveis cadastrados no CAR com supressão vegetal ilegal em Sorocaba", "buscar_imoveis_desmatamento"),
    ("Listar fazendas em Campinas com alertas DETER dentro do perímetro", "buscar_imoveis_desmatamento"),
    ("Fazendas com alerta de supressão vegetal dentro do perímetro do CAR", "buscar_imoveis_desmatamento"),
    ("Quais imóveis têm desmatamento detectado dentro dos limites da propriedade?", "buscar_imoveis_desmatamento"),
    ("Propriedades rurais com corte raso dentro do polígono cadastrado", "buscar_imoveis_desmatamento"),
    ("Quais imóveis rurais têm alertas PRODES dentro do polígono?", "buscar_imoveis_desmatamento"),
    ("CAR de propriedades com supressão vegetal dentro dos limites em Marília", "buscar_imoveis_desmatamento"),
    ("Listar CARs com alertas de corte raso dentro do polígono registrado", "buscar_imoveis_desmatamento"),

    # =========================================================================
    # buscar_imoveis_quilombo
    # =========================================================================
    ("Quais propriedades rurais privadas sobrepõem territórios quilombolas?", "buscar_imoveis_quilombo"),
    ("Imóveis do CAR que cruzam com áreas de quilombo em Eldorado", "buscar_imoveis_quilombo"),
    ("Propriedades rurais que invadem territórios quilombolas no Vale do Ribeira", "buscar_imoveis_quilombo"),
    ("Imóveis do CAR com sobreposição em comunidades quilombolas", "buscar_imoveis_quilombo"),
    ("Fazendas privadas que cruzam com áreas de quilombo em Eldorado", "buscar_imoveis_quilombo"),
    ("Quais cadastros SICAR intersectam territórios quilombolas reconhecidos?", "buscar_imoveis_quilombo"),
    ("Territórios quilombolas no Vale do Ribeira e propriedades rurais sobrepostas", "buscar_imoveis_quilombo"),
    ("Comunidades quilombolas e imóveis do CAR que cruzam com elas", "buscar_imoveis_quilombo"),

    # =========================================================================
    # buscar_imoveis_ti
    # =========================================================================
    ("Existem imóveis rurais invadindo terras indígenas em SP?", "buscar_imoveis_ti"),
    ("Buscar cadastros do SICAR que intersectam a TI Tekoa Pyau", "buscar_imoveis_ti"),
    ("Quais fazendas estão dentro de terras indígenas no estado de SP?", "buscar_imoveis_ti"),
    ("CARs sobrepostos a demarcações indígenas em São Paulo", "buscar_imoveis_ti"),
    ("Imóveis rurais com sobreposição em TIs paulistas", "buscar_imoveis_ti"),
    ("Imóveis rurais cadastrados no CAR que sobrepõem terras indígenas", "buscar_imoveis_ti"),
    ("Fazendas do SICAR dentro do perímetro de TIs homologadas", "buscar_imoveis_ti"),
    ("Mapa de terras indígenas em SP e os imóveis rurais que as sobrepõem", "buscar_imoveis_ti"),
    ("TIs homologadas e fazendas com conflito fundiário no estado", "buscar_imoveis_ti"),
    ("Imóveis rurais que sobrepõem tanto terras indígenas quanto quilombolas", "buscar_imoveis_ti"),

    # =========================================================================
    # buscar_camadas_estaduais
    # =========================================================================
    ("Exibir mapa de zoneamento ambiental do estado de São Paulo", "buscar_camadas_estaduais"),
    ("Quais são os limites das bacias hidrográficas paulistas?", "buscar_camadas_estaduais"),
    ("Camada geomorfológica ou de vulnerabilidade climática da SIMA", "buscar_camadas_estaduais"),
    ("Mostrar o mapa de bacias hidrográficas do estado de São Paulo", "buscar_camadas_estaduais"),
    ("Camadas de uso e cobertura do solo disponíveis no DataGeo SP", "buscar_camadas_estaduais"),
    ("Zoneamento ecológico-econômico do estado de São Paulo", "buscar_camadas_estaduais"),
    ("Mapa de vulnerabilidade ambiental do DataGeo SP", "buscar_camadas_estaduais"),
    ("Zoneamento agroambiental do estado de São Paulo", "buscar_camadas_estaduais"),
    ("Mapa de solos e aptidão agrícola do estado de SP", "buscar_camadas_estaduais"),

    # =========================================================================
    # buscar_imoveis_em_camadas
    # =========================================================================
    ("Quais fazendas estão dentro de áreas de restrição ambiental estadual?", "buscar_imoveis_em_camadas"),
    ("Imóveis do CAR localizados na faixa de amortecimento de parques", "buscar_imoveis_em_camadas"),
    ("Imóveis rurais dentro do perímetro de unidades de conservação", "buscar_imoveis_em_camadas"),
    ("Fazendas do CAR sobrepostas a parques estaduais em SP", "buscar_imoveis_em_camadas"),
    ("Propriedades rurais na faixa de amortecimento de APAs", "buscar_imoveis_em_camadas"),
    ("Fazendas do CAR localizadas em zonas de restrição hídrica em SP", "buscar_imoveis_em_camadas"),
    ("Quais imóveis rurais estão em áreas de vulnerabilidade ambiental estadual?", "buscar_imoveis_em_camadas"),
    ("Parques estaduais e fazendas do CAR dentro do perímetro", "buscar_imoveis_em_camadas"),
    ("Unidades de conservação e imóveis rurais sobrepostos em SP", "buscar_imoveis_em_camadas"),
    ("Quais imóveis rurais estão dentro de APAs no estado de São Paulo?", "buscar_imoveis_em_camadas"),
    ("CARs sobrepostos a RPPNs e reservas biológicas em São Paulo", "buscar_imoveis_em_camadas"),

    # =========================================================================
    # buscar_passivos_imovel
    # =========================================================================
    ("Buscar passivos ambientais do imóvel rural CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40", "buscar_passivos_imovel"),
    ("O imóvel CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40 possui algum passivo ou embargo?", "buscar_passivos_imovel"),
    ("Quais as irregularidades e passivos ambientais na fazenda CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", "buscar_passivos_imovel"),
    ("relatorio de passivos ambientais para o sicar CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40", "buscar_passivos_imovel"),
    ("Quais passivos ambientais existem no imóvel rural com código CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", "buscar_passivos_imovel"),
    ("O imóvel CAR SP-3500105-ABCDEF1234567890ABCDEF1234567890 tem sobreposição com TI ou UC?", "buscar_passivos_imovel"),
    ("Verificar passivos e embargos do CAR SP-3550308-12AB34CD56EF78901234567890ABCDEF", "buscar_passivos_imovel"),

    # =========================================================================
    # buscar_focos_queimada_imovel
    # =========================================================================
    ("Quais foram os focos de queimada detectados no imóvel CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", "buscar_focos_queimada_imovel"),
    ("Histórico de incêndios dentro da propriedade CAR CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40", "buscar_focos_queimada_imovel"),
    ("Houve algum foco de calor registrado na minha fazenda CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", "buscar_focos_queimada_imovel"),
    ("Satélite detectou fogo dentro do imóvel rural CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", "buscar_focos_queimada_imovel"),
    ("Quantas queimadas atingiram o imóvel CAR SP-3500709-F80A461130164CF9A0B0FEAB5611FA40 em 2024?", "buscar_focos_queimada_imovel"),
    ("Houve focos de queimada dentro do imóvel SP-3500709-F80A461130164CF9A0B0FEAB5611FA40?", "buscar_focos_queimada_imovel"),
    ("Incêndios detectados pelo satélite no CAR SP-3550308-12AB34CD56EF78901234567890ABCDEF", "buscar_focos_queimada_imovel"),
    ("Focos de queimada nos últimos 12 meses dentro do CAR SP555666777", "buscar_focos_queimada_imovel"),
    ("Quero saber se houve queimada na minha propriedade SP888777666 este ano", "buscar_focos_queimada_imovel"),

    # =========================================================================
    # buscar_maiores_quantidades
    # =========================================================================
    ("Quais são os municípios com maior número de focos de queimada em SP?", "buscar_maiores_quantidades"),
    ("Qual a região administrativa que mais desmatou em 2024?", "buscar_maiores_quantidades"),
    ("Quais cidades paulistas possuem mais terras indígenas homologadas?", "buscar_maiores_quantidades"),
    ("Ranking de desmatamento DETER por região administrativa", "buscar_maiores_quantidades"),
    ("quais as RAs com maior quantidade de quilombolas no estado?", "buscar_maiores_quantidades"),
    ("maiores focos de incendio por municipio em sao paulo", "buscar_maiores_quantidades"),
    ("Quais os municípios com maiores quantidades de queimadas na RA de Sorocaba?", "buscar_maiores_quantidades"),
    ("ranking de desmatamento na regiao administrativa de marilia", "buscar_maiores_quantidades"),
    ("qual o município que teve o maior foco de queimada?", "buscar_maiores_quantidades"),
    ("qual o município do estado de sp que teve o maior foco de queimada?", "buscar_maiores_quantidades"),
    ("qual município teve o maior número de focos de queimada?", "buscar_maiores_quantidades"),
    ("qual cidade registrou mais focos de incêndio em SP?", "buscar_maiores_quantidades"),
    ("qual é o município com mais queimadas no estado de São Paulo?", "buscar_maiores_quantidades"),
    ("qual município de SP teve mais focos de queimada?", "buscar_maiores_quantidades"),
    ("qual o município paulista com mais focos de calor registrados?", "buscar_maiores_quantidades"),
    ("qual cidade do estado de SP teve mais queimadas?", "buscar_maiores_quantidades"),
    ("qual município lidera o ranking de queimadas em SP?", "buscar_maiores_quantidades"),
    ("qual o município com mais desmatamento no estado de SP?", "buscar_maiores_quantidades"),
    ("qual cidade teve mais alertas de desmatamento em São Paulo?", "buscar_maiores_quantidades"),
    ("qual é a cidade com maior área desmatada em SP?", "buscar_maiores_quantidades"),
    ("qual município paulista teve o maior número de alertas PRODES?", "buscar_maiores_quantidades"),
    ("qual município lidera o ranking de desmatamento no estado de SP?", "buscar_maiores_quantidades"),
    ("qual o município do estado de sp com mais terras indígenas?", "buscar_maiores_quantidades"),
    ("qual cidade de São Paulo concentra mais territórios indígenas?", "buscar_maiores_quantidades"),
    ("qual município paulista tem o maior número de TIs homologadas?", "buscar_maiores_quantidades"),
    ("qual o município do estado de sp com mais unidades de conservação?", "buscar_maiores_quantidades"),
    ("qual cidade paulista concentra mais áreas protegidas?", "buscar_maiores_quantidades"),
    ("qual município de SP tem o maior número de UCs?", "buscar_maiores_quantidades"),
    ("qual cidade do estado tem maior extensão de unidades de conservação?", "buscar_maiores_quantidades"),
    ("qual o município do estado de sp com mais territórios quilombolas?", "buscar_maiores_quantidades"),
    ("qual cidade de São Paulo tem mais comunidades quilombolas?", "buscar_maiores_quantidades"),
    ("qual o município do estado de sp com mais imóveis rurais cadastrados?", "buscar_maiores_quantidades"),
    ("qual cidade paulista tem mais propriedades rurais no CAR?", "buscar_maiores_quantidades"),
    ("Top 10 municípios com mais focos de queimada no estado", "buscar_maiores_quantidades"),
    ("Quais são as RAs com maior número de terras indígenas?", "buscar_maiores_quantidades"),
    ("Municípios com mais territórios quilombolas em SP", "buscar_maiores_quantidades"),
    ("Ranking de municípios com mais unidades de conservação em SP", "buscar_maiores_quantidades"),
    ("Quais municípios têm mais alertas PRODES em SP?", "buscar_maiores_quantidades"),
    ("Top 5 cidades com maior área desmatada no estado de São Paulo", "buscar_maiores_quantidades"),
    ("Quais municípios lideram o desmatamento em São Paulo?", "buscar_maiores_quantidades"),
    ("Quais municípios concentram mais TIs e UCs sobrepostas em SP?", "buscar_maiores_quantidades"),
    ("Ranking de municípios com maior sobreposição entre terras indígenas e unidades de conservação em SP", "buscar_maiores_quantidades"),

    # =========================================================================
    # buscar_documentos
    # =========================================================================
    ("Quais são as regras para o licenciamento ambiental de desmatamento?", "buscar_documentos"),
    ("Como funciona a regularização de passivo ambiental no PRA?", "buscar_documentos"),
    ("Legislação sobre queima controlada de cana-de-açúcar em SP", "buscar_documentos"),
    ("Quais leis regulamentam a queima de vegetação nativa em SP?", "buscar_documentos"),
    ("O que é o Programa de Regularização Ambiental do estado?", "buscar_documentos"),
    ("Qual a legislação sobre áreas de preservação permanente no Brasil?", "buscar_documentos"),
    ("Documentos sobre o PRODES e sua metodologia de detecção de desmatamento", "buscar_documentos"),
    ("Normativas do IBAMA para o monitoramento de queimadas e incêndios", "buscar_documentos"),
    ("Como funciona o CAR e o SICAR no estado de São Paulo?", "buscar_documentos"),
    ("Qual a resolução CONAMA sobre desmatamento em Mata Atlântica?", "buscar_documentos"),
    ("Legislação federal sobre proteção de terras indígenas", "buscar_documentos"),
    ("Quais são os critérios para homologação de territórios quilombolas?", "buscar_documentos"),
    ("Resolução SMA sobre unidades de conservação estaduais em SP", "buscar_documentos"),
    ("O que é o Código Florestal Brasileiro e como ele se aplica em SP?", "buscar_documentos"),
    ("Como funciona o programa BDQueimadas do INPE?", "buscar_documentos"),
    ("Explique como o SNUC classifica as unidades de conservação", "buscar_documentos"),
    ("Quais são as penalidades para desmatamento ilegal na Mata Atlântica?", "buscar_documentos"),
    ("O que diz a lei da Mata Atlântica sobre supressão de vegetação?", "buscar_documentos"),
    ("Como é feita a demarcação de territórios quilombolas pelo INCRA?", "buscar_documentos"),
    ("Normativa sobre reserva legal em imóveis rurais no estado de SP", "buscar_documentos"),
    ("Explique a metodologia do PRODES para detecção de desmatamento", "buscar_documentos"),
    ("Qual legislação define as zonas de amortecimento de parques estaduais?", "buscar_documentos"),

    # =========================================================================
    # fora_escopo
    # =========================================================================
    ("Qual a previsão do tempo para a capital amanhã?", "fora_escopo"),
    ("Quais são as notícias sobre futebol em Campinas?", "fora_escopo"),
    ("Queimadas no Pantanal mato-grossense", "fora_escopo"),
    ("Qual o preço do boi gordo hoje?", "fora_escopo"),
    ("Me fale sobre a história do Brasil", "fora_escopo"),
    ("Dados ambientais do estado do Paraná", "fora_escopo"),
    ("Terras indígenas no Pará", "fora_escopo"),
    ("Como está a seca no Nordeste?", "fora_escopo"),
    ("Dados climáticos do Rio de Janeiro", "fora_escopo"),
    ("Qual o partido político mais votado em SP?", "fora_escopo"),
    ("Cotação do dólar hoje", "fora_escopo"),
    ("Unidades de conservação no Amazonas", "fora_escopo"),
    ("queimadas no cerrado goias", "fora_escopo"),
    ("desmatamento amazonia para 2024", "fora_escopo"),
    ("terras indigenas mato grosso", "fora_escopo"),
    ("assentamentos incra minas gerais", "fora_escopo"),
    ("unidades conservacao rio de janeiro", "fora_escopo"),
    ("previsao chuva campinas semana", "fora_escopo"),
    ("preco soja commodities hoje", "fora_escopo"),
    ("eleicoes municipais sp resultado", "fora_escopo"),
    ("temperatura media ribeirao preto", "fora_escopo"),
    ("dados demograficos sao paulo ibge", "fora_escopo"),
    ("territórios quilombolas no Pará", "fora_escopo"),
    ("terras indígenas na Amazônia", "fora_escopo"),
    ("queimadas no Pantanal do Mato Grosso do Sul", "fora_escopo"),
    ("desmatamento na Amazônia Legal em 2024", "fora_escopo"),
    ("unidades de conservação no Mato Grosso", "fora_escopo"),
    ("focos de incêndio no Cerrado do Tocantins", "fora_escopo"),
    ("assentamentos do INCRA em Minas Gerais", "fora_escopo"),
    ("imóveis rurais no CAR do estado do Paraná", "fora_escopo"),
    ("alertas DETER na Amazônia Legal", "fora_escopo"),
    ("quilombolas reconhecidos na Bahia pelo INCRA", "fora_escopo"),
]
