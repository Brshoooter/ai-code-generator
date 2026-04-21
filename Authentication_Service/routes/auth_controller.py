from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from models.schemas import RegisterRequest, LoginRequest, TokenResponse
from services.auth_service import register_user, login_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return register_user(data, db)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return login_user(data, db)
