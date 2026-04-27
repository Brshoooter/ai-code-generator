import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # user_id vine din claim-ul 'sub' al JWT — NU este foreign key
    # pentru ca tabela users traieste intr-un alt container Postgres
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(100), nullable=False, default="New Conversation")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # relatie one-to-many: o conversatie are multe mesaje
    # cascade="all, delete-orphan" inseamna ca stergerea conversatiei sterge si mesajele
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ON DELETE CASCADE la nivel DB (redundant cu cascade ORM, dar mai sigur)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "user" sau "assistant" — validat si la nivel Pydantic
    role = Column(String(20), nullable=False)
    # Text (nu String) pentru ca raspunsurile LLM pot fi oricate de lungi
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


# index compus pentru sortarea rapida a mesajelor dintr-o conversatie
Index("ix_messages_conv_created", Message.conversation_id, Message.created_at)
