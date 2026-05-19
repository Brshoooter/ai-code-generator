import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config import settings
from database.database import Base, engine, ensure_pgvector_extension
# Importul modelelor e OBLIGATORIU inainte de create_all — altfel Base.metadata
# nu stie de clasele FileRecord / FileChunk si nu creeaza tabelele.
from models import file_model  # noqa: F401
from routes.files_controller import router
from services.sd_client import SDClient


logger = logging.getLogger(__name__)
sd_client = SDClient()


async def _check_ollama_model() -> None:
    """
    Verifica la pornire daca modelul de embeddings exista in Ollama.

    Apeleaza GET /api/tags si cauta un model al carui nume incepe cu
    settings.embedding_model (ex. "nomic-embed-text" prinde si
    "nomic-embed-text:latest").

    NU oprim serviciul daca lipseste — log warning, ca utilizatorul sa
    poata rula "ollama pull nomic-embed-text" si reincerca un upload
    fara sa restartam containerul. Endpointurile fara embeddings
    (list, delete, download, health) raman functionale oricum.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.warning(
            f"Ollama indisponibil la {settings.ollama_base_url} ({e}). "
            "Uploadurile cu embedding vor esua pana cand Ollama porneste."
        )
        return

    # Raspunsul are forma {"models": [{"name": "nomic-embed-text:latest", ...}, ...]}
    names = [m.get("name", "") for m in data.get("models", [])]
    if any(n.startswith(settings.embedding_model) for n in names):
        logger.info(
            f"Ollama pregatit: modelul '{settings.embedding_model}' este disponibil."
        )
    else:
        logger.warning(
            f"Modelul '{settings.embedding_model}' lipseste din Ollama. "
            f"Modele gasite: {names}. "
            f"Ruleaza: ollama pull {settings.embedding_model}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Activeaza extensia pgvector (necesar inainte de create_all,
    #    pentru ca tabela file_chunks are coloana Vector(768))
    ensure_pgvector_extension()
    # 2. Creeaza tabelele "files" si "file_chunks" daca nu exista
    Base.metadata.create_all(bind=engine)
    # 3. Pre-flight: avem modelul de embeddings in Ollama? (doar warning daca nu)
    await _check_ollama_model()
    # 4. Anunta Service Discovery ca suntem online
    await sd_client.register()
    yield
    await sd_client.deregister()


app = FastAPI(
    title="FilesService",
    description="Microserviciu pentru fisiere atasate conversatiilor (RAG + S3)",
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

app.include_router(router, tags=["Fisiere"])


@app.get("/health", tags=["Health"])
def health_check():
    """
    Verifica starea serviciului si conexiunea la baza de date.
    Service Discovery loveste acest endpoint la fiecare 30s.
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
