from pydantic import BaseModel, Field

class GenerateRequest(BaseModel):
    prompt: str=Field(
        min_length=1,
        description="prompt- ul utilizatorului pentru generarea de cod"
    )