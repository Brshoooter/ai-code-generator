from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class GenerateRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    # ID-ul conversatiei curente. Optional pentru retro-compatibilitate:
    # request-urile vechi (fara fisiere) merg in continuare fara el. Cand e
    # setat, Chat Service cere context RAG de la Files Service inainte de
    # a genera raspunsul. Optional[UUID] = poate fi UUID sau None.
    conversation_id: Optional[UUID] = None