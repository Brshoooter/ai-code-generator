import jwt
from fastapi import Header, HTTPException, status

from config import settings

# cheia publica se citeste o singura data la pornirea serviciului
# History Service nu are private key — doar verifica tokenuri, nu le semneaza
with open(settings.jwt_public_key_path, "r") as f:
    PUBLIC_KEY = f.read()


def get_current_user_id(authorization: str = Header(...)) -> str:
    """
    Dependency FastAPI — injectat cu Depends(get_current_user_id) in fiecare ruta protejata.
    Citeste header-ul Authorization, verifica semnatura JWT si returneaza user_id (claim 'sub').

    Gateway-ul a verificat deja tokenul, dar verificam si noi (defense in depth):
    daca cineva apeleaza serviciul direct in reteaua Docker, tot trebuie token valid.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Format token invalid")

    token = authorization[len("Bearer "):]

    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirat")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalid")

    return payload["sub"]
