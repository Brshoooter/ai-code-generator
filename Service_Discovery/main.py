from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from routes import router, registry
from health_checker import HealthChecker
from config import settings

@asynccontextmanager
async def lifespan(app):

    checker = HealthChecker(registry)
    task = asyncio.create_task(checker.checking_health())

    yield

    await checker.stop()
    task.cancel()

app = FastAPI(
    title = "Service Discovery",
    description = "Serviciu central pentru inregistrare si descoperire microservicii",
    version = "0.1.0",
    lifespan = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["Service Discovery"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)