from datetime import datetime, timezone, timedelta

import jwt

from config import settings

#Se citeste cheia privata o singura data la pornirea serviciului
with open(settings.jwt_private_key_path, "r") as f:
    PRIVATE_KEY = f.read()


def create_token(user_id: str, username: str) -> str:
    """
    Creeaza un JWT semnat cu cheia privata RSA (RS256).
    """
    acum = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": acum,
        "exp": acum + timedelta(minutes=settings.jwt_expiry_minutes)
    }

    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
