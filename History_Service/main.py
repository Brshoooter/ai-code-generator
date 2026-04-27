from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config import settings
from database.database import engine, Base
from models import conversation_model
from routes.history_controller import router
from services.sd_client import SDClient


sd_client = SDClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # creeaza tabelele conversations si messages daca nu exista
    Base.metadata.create_all(bind=engine)
    await sd_client.register()
    yield
    await sd_client.deregister()


app = FastAPI(
    title="HistoryService",
    description="Microserviciu de istoric al conversatiilor cu JWT si PostgreSQL",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, tags=["Istoric"])


@app.get("/health", tags=["Health"])
def health_check():
    """
    Verifica starea serviciului si conexiunea la baza de date.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "service": settings.service_name, "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": settings.service_name,
                "database": "unreachable",
                "detail": str(e),
            },
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
