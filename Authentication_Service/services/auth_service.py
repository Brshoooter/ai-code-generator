import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user_model import User
from models.schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from services.jwt_handler import create_token




def register_user(data: RegisterRequest, db: Session) -> TokenResponse:

    """
    Functia de inregistrare a unui utilizator nou
    """
    #verificare daca exista deja username sau email in DB
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username-ul este deja folosit.",
        )
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email-ul este deja folosit.",
        )

    #hash parola cu bcrypt
    hashed_password = bcrypt.hashpw(
        data.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    #Creeaza si salveaza userul
    new_user = User(
        username=data.username,
        email=data.email,
        password=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Pasul 4: genereaza JWT si returneaza raspunsul
    token = create_token(user_id=str(new_user.id), username=new_user.username)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(new_user),
    )


def login_user(data: LoginRequest, db: Session) -> TokenResponse:

    """
    Functia de autentificare a unui utilizator existent
    """
    #cauta userul in DB dupa username SAU email
    user = db.query(User).filter(
        (User.username == data.username) | (User.email == data.username)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username sau parola incorecte.",
        )

    #verificare parola
    parola_ok = bcrypt.checkpw(data.password.encode("utf-8"), user.password.encode("utf-8"))
    if not parola_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username sau parola incorecte.",
        )

    #genereaza JWT si returneaza raspunsul
    token = create_token(user_id=str(user.id), username=user.username)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )