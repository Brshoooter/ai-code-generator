import logging

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

from config import settings

logger = logging.getLogger(__name__)

# Cheia publica se citeste o singura data la import.
with open(settings.jwt_public_key_path, "r") as f:
    PUBLIC_KEY = f.read()

# Rute care nu necesita JWT.
PUBLIC_PATHS = {
    "/health",
    "/api/auth-service/register",
    "/api/auth-service/login",
}


class JWTMiddleware:

    async def verify_jwt(self, request: Request, call_next):
        """
        Verifica token-ul JWT pe rutele protejate.
        Rutele din PUBLIC_PATHS trec fara verificare.
        """
        # Permite preflight CORS fara JWT
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token lipsa. Autentifica-te pentru a continua."},
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Format token invalid. Se asteapta: Bearer <token>"},
            )

        token = auth_header[len("Bearer "):]

        try:
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
            request.state.user = payload
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token expirat. Fa login din nou."},
            )
        except jwt.InvalidTokenError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token invalid."},
            )

        return await call_next(request)
