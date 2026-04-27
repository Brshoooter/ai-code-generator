from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MessageCreate(BaseModel):
    # Literal refuza la runtime orice alta valoare in afara de "user" sau "assistant"
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        """Converteste UUID-ul din SQLAlchemy in string pentru raspunsul JSON."""
        if isinstance(v, UUID):
            return str(v)
        return v


class ConversationCreate(BaseModel):
    # titlul e optional — daca nu e trimis, serviciul il seteaza la "New Conversation"
    title: str | None = None


class ConversationSummary(BaseModel):
    """Folosit in lista din sidebar — fara mesaje, doar metadate."""
    id: str
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class ConversationResponse(BaseModel):
    """Folosit cand se deschide o conversatie — include si lista de mesaje."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    class Config:
        from_attributes = True

    @field_validator("id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v
