from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    """Date trimise de utilizator la inregistrare."""
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    """Date trimise de utilizator la autentificare."""
    username: str
    password: str


class UserResponse(BaseModel):
    """
    Datele utilizatorului returnate in raspuns
    """
    id: str
    username: str
    email: str

    """" 
    Pydantic poate lua direct atributele dintr-un obiect sa le valideze
    """
    class Config:
        from_attributes = True

    @field_validator("id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        """Converteste UUID-ul din SQLAlchemy in string pentru raspunsul JSON."""
        if isinstance(v, UUID):
            return str(v)
        return v


class TokenResponse(BaseModel):
    """Raspunsul complet dupa login sau register cu succes."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
