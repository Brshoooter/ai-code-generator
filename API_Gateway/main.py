from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes import router
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limiter import RateLimiter
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

@app.middleware("http")
async def middleware_chain(request: Request, call_next):
    if not rate_limiter.is_allowed(request.client.host):
        return JSONResponse(
            status_code=429,
            content={"detail": "Prea multe request-uri. Incearca mai tarziu."}
        )

    return await logging_middleware.logging_request(request, call_next)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)