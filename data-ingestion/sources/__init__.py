"""
Sources - Implementações específicas de pipelines ETL por fonte de dados.

Cada fonte tem sua própria implementação, mas segue o padrão:
  - create_pipeline() → retorna BasePipeline

Exemplo:
  from sources.icmbio import create_pipeline
  pipeline = create_pipeline(engine, wfs_client, config)
  result = pipeline.run()
"""
