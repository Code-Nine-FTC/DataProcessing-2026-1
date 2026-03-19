import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from geoalchemy2 import Geometry
from .base import Base


class Conceito(Base):
    __tablename__ = "conceito"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_canonico = Column(Text)
    tipo_conceito = Column(Text)


class ConceitoAlias(Base):
    __tablename__ = "conceito_alias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conceito_id = Column(UUID(as_uuid=True), ForeignKey("conceito.id", deferrable=True, initially="IMMEDIATE"))
    alias = Column(Text)


class IntencaoConsulta(Base):
    __tablename__ = "intencao_consulta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(Text)
    descricao = Column(Text)


class Documento(Base):
    __tablename__ = "documento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id", deferrable=True, initially="IMMEDIATE"))
    titulo = Column(Text)
    tipo = Column(Text)
    texto_integral = Column(Text)
    url_origem = Column(Text)
    metadata_json = Column(JSONB)


class DocumentoTrecho(Base):
    __tablename__ = "documento_trecho"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documento.id", deferrable=True, initially="IMMEDIATE"))
    ordem = Column(Integer)
    texto = Column(Text)
    embedding = Column(Vector(768))
    tokens_count = Column(Integer)


class Chat(Base):
    __tablename__ = "chat"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text)
    created_at = Column(DateTime)


class ConsultaUsuario(Base):
    __tablename__ = "consulta_usuario"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pergunta = Column(Text)
    data_hora = Column(DateTime)
    intencao_id = Column(UUID(as_uuid=True), ForeignKey("intencao_consulta.id", deferrable=True, initially="IMMEDIATE"))
    intencao_score = Column(Numeric)
    entidades_detectadas_json = Column(JSONB)
    filtros_detectados_json = Column(JSONB)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chat.id", deferrable=True, initially="IMMEDIATE"))
    turno = Column(Integer)


class RespostaSistema(Base):
    __tablename__ = "resposta_sistema"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consulta_usuario_id = Column(UUID(as_uuid=True), ForeignKey("consulta_usuario.id", deferrable=True, initially="IMMEDIATE"))
    texto_resposta = Column(Text)
    sql_executado = Column(Text)
    fontes_utilizadas_json = Column(JSONB)
    bbox_resultado = Column(Geometry("POLYGON", srid=4326))
    tempo_resposta_ms = Column(Integer)
    status = Column(Text, default="sucesso")
    mensagem_erro = Column(Text)


class FeedbackResposta(Base):
    __tablename__ = "feedback_resposta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resposta_sistema_id = Column(UUID(as_uuid=True), ForeignKey("resposta_sistema.id", deferrable=True, initially="IMMEDIATE"), nullable=False)
    avaliacao = Column(SmallInteger)
    comentario = Column(Text)
data_hora = Column(DateTime)
