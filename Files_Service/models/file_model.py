import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from database.database import Base
from config import settings


# ─────────────────────────────────────────────────────────────────
# Tabela "files"
# ─────────────────────────────────────────────────────────────────
# Fiecare rand reprezinta un fisier urcat de un utilizator intr-o
# conversatie. user_id este claim-ul "sub" din JWT, NU un foreign key
# (tabela "users" e in alt Postgres — auth_db). conversation_id la fel
# nu e FK, conversatiile traiesc in history_db.
#
# s3_key e calea sub care fisierul e salvat in S3 (sau in stub local pe
# disk in faza de dezvoltare). Format: "{user_id}/{conv_id}/{file_id}-{nume}".
class FileRecord(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=False)
    s3_key = Column(Text, nullable=False, unique=True)
    original_name = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default="ready")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # cascade pe DELETE: cand stergem un FileRecord, chunk-urile dispar automat
    chunks = relationship(
        "FileChunk",
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Index compus pentru "listeaza fisierele din conversatia X ale userului Y"
        Index("ix_files_user_conv", "user_id", "conversation_id"),
        # Index simplu pentru calculul cotei totale per user (SUM(size_bytes))
        Index("ix_files_user", "user_id"),
    )


# ─────────────────────────────────────────────────────────────────
# Tabela "file_chunks"
# ─────────────────────────────────────────────────────────────────
# Un fisier dupa extragere si chunking devine N randuri aici. "embedding"
# e un vector de 768 floats (output-ul modelului nomic-embed-text rulat
# prin Ollama). Tipul Vector vine din pachetul "pgvector" si se mapeaza
# la tipul SQL VECTOR(768) din extensia pgvector.
#
# Indexul ivfflat (vezi Index-ul de mai jos):
#   - "ivf" = Inverted File Index, "flat" = stocheaza vectorii bruti, fara compresie
#   - imparte vectorii in "lists" centroizi (100 e un default rezonabil pentru
#     volume mici)
#   - la cautare scaneaza doar centroizii apropiati de query, nu tot tabelul
#   - operator class "vector_cosine_ops" inseamna distanta cosine (<=> in SQL)
#   - alternativa ar fi HNSW (mai rapid la query, mai lent la insert) — ivfflat
#     e suficient pentru zeci de mii de chunks
class FileChunk(Base):
    __tablename__ = "file_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.embedding_dim), nullable=False)

    file = relationship("FileRecord", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_file", "file_id"),
        # Indexul ivfflat se creeaza separat in lifespan dupa create_all,
        # pentru ca SQLAlchemy nu stie nativ sa emita "USING ivfflat (...)
        # WITH (lists = 100)". Vezi main.py — Etapa 2 pas 4.
    )
