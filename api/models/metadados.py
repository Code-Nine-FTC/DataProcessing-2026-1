import uuid
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from .base import Base


class FonteDado(Base):
    __tablename__ = "fonte_dado"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(Text, nullable=False)
    orgao_responsavel = Column(Text)
    url_origem = Column(Text)
    formato = Column(Text)
    periodicidade = Column(Text)
    escopo_geografico = Column(Text)
    licenca = Column(Text)
    ativo = Column(Boolean, default=True)

    datasets = relationship("Dataset", back_populates="fonte_dado")


class Dataset(Base):
    __tablename__ = "dataset"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fonte_dado_id = Column(UUID(as_uuid=True), ForeignKey("fonte_dado.id", deferrable=True, initially="IMMEDIATE"))
    nome = Column(Text, nullable=False)
    descricao = Column(Text)
    versao = Column(Text)
    data_coleta = Column(DateTime)
    data_referencia = Column(Date)
    hash_arquivo = Column(Text)
    caminho_arquivo = Column(Text)
    metadata_json = Column(JSONB)

    fonte_dado = relationship("FonteDado", back_populates="datasets")
    processamentos = relationship("Processamento", back_populates="dataset")


class Processamento(Base):
    __tablename__ = "processamento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    tipo_processamento = Column(Text)
    data_execucao = Column(DateTime)
    status = Column(Text)
    log_execucao = Column(Text)
    parametros_json = Column(JSONB)

    dataset = relationship("Dataset", back_populates="processamentos")
