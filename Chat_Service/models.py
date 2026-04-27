from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class GenerateRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)