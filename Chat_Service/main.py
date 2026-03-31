from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import httpx
from routes.generate_controller import router
from config import settings
from services.sd_client import SDClient


sd_client = SDClient()

@asynccontextmanager
async def lifespan(app):
    await sd_client.register()
    yield
    await sd_client.deregister()

app = FastAPI(
    title="GenerateService",
    description="microserviciu pentru generarea codului",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/generate", tags=["Code Generation"])

@app.get("/health", tags=["Health"])
async def health_check():
    ollama_ok = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=5
            )
            ollama_ok = response.status_code == 200
    except Exception:
        ollama_ok = False
 
    if ollama_ok:
        return {"status": "healthy", "service": settings.service_name, "ollama": "connected"}
 
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "service": settings.service_name, "ollama": "unreachable"}
    )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)