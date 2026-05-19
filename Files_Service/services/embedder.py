"""
Client HTTP catre Ollama pentru generare de embeddings.

Scop: dat un text (un chunk dintr-un fisier urcat sau un query de cautare),
returneaza un vector de "embedding_dim" floats (768 pentru nomic-embed-text).
Vectorii ajung apoi in coloana VECTOR(768) din file_chunks si sunt comparati
cu operatorul cosine "<=>" la retrieval.

De ce httpx direct si NU langchain-ollama:
  - Avem nevoie doar de un singur endpoint POST /api/embeddings — un wrapper
    LangChain ar adauga dependinte si abstractii pe care nu le folosim.
  - Async-ul nativ httpx se integreaza curat cu FastAPI; pentru chunking de
    zeci de bucati, putem astepta fiecare cerere fara sa blocam event loop-ul.

De ce serial si NU paralel:
  - Ollama-ul ruleaza modelul pe CPU/GPU local. Daca trimitem 10 cereri
    concurente, ele se serializeaza oricum in spatele scenei (un singur
    proces de inference). Concurenta in client doar adauga overhead.
  - Cand vom avea Ollama cu batching real, putem reveni aici si paraleliza.

Apelat de:
  - rag_service.ingest_file → embed pentru fiecare chunk al fisierului urcat
  - rag_service.retrieve   → embed pentru query-ul de cautare
"""

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """
    Wrapper subtire peste Ollama /api/embeddings.

    Tinem un singur client per instanta de proces — il instantiem o data
    in rag_service si il refolosim. Fiecare apel deschide totusi un
    AsyncClient nou (vezi nota de mai jos despre lifecycle).
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        dim: int | None = None,
    ):
        # Default-urile vin din settings — argumentele explicite ne lasa sa
        # injectam alte valori la testare (de ex. mock server pe alt port).
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.embedding_model
        self.dim = dim or settings.embedding_dim

    async def embed_one(self, text: str) -> list[float]:
        """
        Trimite un singur text si returneaza vectorul.

        Body-ul Ollama: {"model": "...", "prompt": "..."}
        Raspunsul: {"embedding": [float, float, ...]}

        Timeout 30s — embedding-urile ruleaza pe CPU si pot dura cateva
        secunde per chunk pe masini slabe; 30s ne lasa o margine confortabila.
        """
        # Ollama refuza prompt gol cu 400 — protejam noi inainte sa loveasca
        # reteaua. Returnam vector zero ca chunk-ul gol sa nu strice insertul,
        # desi caller-ul ar trebui sa filtreze chunk-urile goale inainte.
        if not text or not text.strip():
            logger.warning("embed_one chemat cu text gol — returnez vector zero")
            return [0.0] * self.dim

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()

        vec = data.get("embedding")
        if vec is None:
            raise RuntimeError(
                f"Raspuns Ollama fara cheia 'embedding': {data}"
            )
        if len(vec) != self.dim:
            # Daca cineva schimba modelul fara sa updateze settings.embedding_dim,
            # vrem sa pice loud aici, NU sa scriem vectori de alta dimensiune
            # in coloana VECTOR(768) (Postgres ar respinge oricum, dar mesajul
            # nostru e mai clar).
            raise RuntimeError(
                f"Dimensiune embedding gresita: astept {self.dim}, primit {len(vec)}. "
                f"Verifica FILES_EMBEDDING_MODEL si FILES_EMBEDDING_DIM."
            )
        return vec

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """
        Embeddinguri pentru o lista de texte. Apel serial — vezi nota din
        docstring-ul modulului despre de ce nu paralelizam.

        Daca un singur chunk pica (timeout, model lipsa), exceptia se propaga
        si caller-ul (rag_service) face rollback la S3 + nu insereaza nimic
        in DB. Asta evita starea inconsistenta "fisier salvat dar fara unele
        chunks".
        """
        result: list[list[float]] = []
        for i, t in enumerate(texts):
            vec = await self.embed_one(t)
            result.append(vec)
            # log la fiecare 10 chunks ca sa stim ca progreseaza
            if (i + 1) % 10 == 0:
                logger.info(f"Embedding progress: {i + 1}/{len(texts)} chunks")
        return result
