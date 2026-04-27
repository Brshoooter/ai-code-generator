from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes import router
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limiter import RateLimiter
from middleware.auth_middleware import JWTMiddleware
from config import settings

app = FastAPI(
    title="API Gateway",
    description="Poarta catre orice microserviciu din aplicatie",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging_middleware = LoggingMiddleware()
rate_limiter = RateLimiter()
jwt_middleware = JWTMiddleware()


@app.middleware("http")
async def middleware_chain(request: Request, call_next):
    # Preflight CORS si health check nu se contorizeaza si nu cer JWT.
    if request.method == "OPTIONS" or request.url.path == "/health":
        return await call_next(request)

    async def dupa_jwt(req: Request):
        # In acest punct, daca ruta era protejata si tokenul valid, avem req.state.user_id.
        # Daca ruta era publica (login/register), nu avem user_id -> bucket pe IP.
        user_id = getattr(req.state, "user_id", None)

        if user_id:
            allowed = rate_limiter.allow_user(user_id)
        else:
            allowed = rate_limiter.allow_anon(req.client.host)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Prea multe request-uri. Incearca mai tarziu."}
            )

        return await logging_middleware.logging_request(req, call_next)

    return await jwt_middleware.verify_jwt(request, dupa_jwt)


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
