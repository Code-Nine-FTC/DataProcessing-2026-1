import uuid
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .base import Base


class Estado(Base):
    __tablename__ = "estado"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sigla = Column(String(2))
    nome = Column(Text)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))

    municipios = relationship("Municipio", back_populates="estado")


class Municipio(Base):
    __tablename__ = "municipio"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_ibge = Column(String(10))
    nome = Column(Text)
    estado_id = Column(Integer, ForeignKey("estado.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))

    estado = relationship("Estado", back_populates="municipios")


class GradeEspacial(Base):
    __tablename__ = "grade_espacial"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(Text)
    resolucao = Column(Text)
    geom = Column(Geometry("POLYGON", srid=4326))


class BaciaHidrografica(Base):
    __tablename__ = "bacia_hidrografica"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(Text)
    codigo = Column(Text)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))


class ImovelRural(Base):
    __tablename__ = "imovel_rural"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    nome_imovel = Column(Text)
    codigo_car = Column(Text)
    area_ha = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    situacao_cadastral = Column(Text)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    centroid = Column(Geometry("POINT", srid=4326))
    atributos_json = Column(JSONB)


class QueimadaEvento(Base):
    __tablename__ = "queimada_evento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    data_ocorrencia = Column(DateTime)
    fonte_sensor = Column(Text)
    intensidade = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    bioma = Column(Text)
    dias_sem_chuva = Column(Integer)
    precipitacao_mm = Column(Numeric)
    risco_fogo = Column(Numeric)
    geom = Column(Geometry("POINT", srid=4326))
    atributos_json = Column(JSONB)


class DesmatamentoAlerta(Base):
    __tablename__ = "desmatamento_alerta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    data_ocorrencia = Column(Date)
    tipo_alerta = Column(Text)
    area_ha = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json = Column(JSONB)


class UnidadeConservacao(Base):
    __tablename__ = "unidade_conservacao"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    nome = Column(Text)
    categoria = Column(Text)
    esfera = Column(Text)
    grupo_snuc = Column(Text)
    area_ha = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json = Column(JSONB)


class TerraIndigena(Base):
    __tablename__ = "terra_indigena"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    nome = Column(Text)
    fase = Column(Text)
    area_ha = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json = Column(JSONB)


class AssentamentoRural(Base):
    __tablename__ = "assentamento_rural"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    nome = Column(Text)
    modalidade = Column(Text)
    familias = Column(Integer)
    area_ha = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json = Column(JSONB)


class TerritorioQuilombola(Base):
    __tablename__ = "territorio_quilombola"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    nome = Column(Text)
    status_processo = Column(Text)
    area_ha = Column(Numeric)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json = Column(JSONB)


class CamadaEstadualAmbiental(Base):
    __tablename__ = "camada_estadual_ambiental"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_origem = Column(Text)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    tema = Column(Text)
    subtipo = Column(Text)
    nome = Column(Text)
    municipio_id = Column(Integer, ForeignKey("municipio.id", deferrable=True, initially="IMMEDIATE"))
    geom = Column(Geometry("GEOMETRYCOLLECTION", srid=4326))
    atributos_json = Column(JSONB)


# ---------- Tabelas de relacionamento (rel_*) ----------

class RelImovelQueimada(Base):
    __tablename__ = "rel_imovel_queimada"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"))
    queimada_evento_id = Column(UUID(as_uuid=True), ForeignKey("queimada_evento.id", deferrable=True, initially="IMMEDIATE"))
    distancia_m = Column(Numeric)
    dentro_imovel = Column(Text)
    data_calculo = Column(DateTime)


class RelImovelDesmatamento(Base):
    __tablename__ = "rel_imovel_desmatamento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"))
    desmatamento_alerta_id = Column(UUID(as_uuid=True), ForeignKey("desmatamento_alerta.id", deferrable=True, initially="IMMEDIATE"))
    area_intersecao_ha = Column(Numeric)
    percentual_sobreposicao = Column(Numeric)
    data_calculo = Column(DateTime)


class RelImovelUC(Base):
    __tablename__ = "rel_imovel_uc"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"))
    unidade_conservacao_id = Column(UUID(as_uuid=True), ForeignKey("unidade_conservacao.id", deferrable=True, initially="IMMEDIATE"))
    area_intersecao_ha = Column(Numeric)
    percentual_sobreposicao = Column(Numeric)
    tipo_relacao = Column(Text)


class RelImovelTI(Base):
    __tablename__ = "rel_imovel_ti"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"))
    terra_indigena_id = Column(UUID(as_uuid=True), ForeignKey("terra_indigena.id", deferrable=True, initially="IMMEDIATE"))
    area_intersecao_ha = Column(Numeric)
    percentual_sobreposicao = Column(Numeric)
    tipo_relacao = Column(Text)


class RelImovelAssentamento(Base):
    __tablename__ = "rel_imovel_assentamento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"))
    assentamento_rural_id = Column(UUID(as_uuid=True), ForeignKey("assentamento_rural.id", deferrable=True, initially="IMMEDIATE"))
    area_intersecao_ha = Column(Numeric)
    percentual_sobreposicao = Column(Numeric)
    tipo_relacao = Column(Text)


class RelImovelQuilombo(Base):
    __tablename__ = "rel_imovel_quilombo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"))
    territorio_quilombola_id = Column(UUID(as_uuid=True), ForeignKey("territorio_quilombola.id", deferrable=True, initially="IMMEDIATE"))
    area_intersecao_ha = Column(Numeric)
    percentual_sobreposicao = Column(Numeric)
    tipo_relacao = Column(Text)


class RelImovelBacia(Base):
    __tablename__ = "rel_imovel_bacia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_rural_id = Column(UUID(as_uuid=True), ForeignKey("imovel_rural.id", deferrable=True, initially="IMMEDIATE"), nullable=False)
    bacia_hidrografica_id = Column(Integer, ForeignKey("bacia_hidrografica.id", deferrable=True, initially="IMMEDIATE"), nullable=False)
    area_intersecao_ha = Column(Numeric)
    percentual_sobreposicao = Column(Numeric)
    tipo_relacao = Column(Text)
