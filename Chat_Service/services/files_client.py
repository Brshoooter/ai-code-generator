"""
Client HTTP catre Files Service pentru retrieval RAG.

Chat Service nu a chemat niciun alt microserviciu pana acum (vorbea doar
cu Ollama). Acum, cand un request are conversation_id, intrebam Files
Service ce fragmente din fisierele utilizatorului sunt relevante pentru
ultima intrebare, ca sa le injectam in prompt.

De ce un fisier separat (nu logica in controller):
  - Controllerul ramane subtire (conventia MVC din CLAUDE.md).
  - Izolam aici atat rezolvarea URL-ului prin Service Discovery, cat si
    apelul HTTP propriu-zis.

Best-effort: ORICE esec (Service Discovery cazut, files-service indisponibil,
raspuns non-200, timeout) returneaza [] — chat-ul trebuie sa functioneze
normal chiar daca RAG-ul pica. Nu propagam exceptii in fluxul de generare.
"""

import logging
from uuid import UUID

import httpx

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Numele sub care files-service se inregistreaza in Service Discovery.
# Trebuie sa fie identic cu service_name din Files_Service/config.py.
FILES_SERVICE_NAME = "files-service"


async def _resolve_files_url() -> str | None:
    """
    Intreaba Service Discovery unde ruleaza files-service.

    GET {sd_url}/api/services/{name} → lista de instante [{"url": ...}, ...],
    exact endpointul pe care il foloseste si discovery_client din Gateway.
    Luam prima instanta (fara round-robin — in dev avem un singur container).
    Returneaza None daca SD e cazut sau nu exista instante vii.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.sd_url}/api/services/{FILES_SERVICE_NAME}"
            )
            if response.status_code != 200:
                logger.warning(
                    f"Service Discovery a raspuns {response.status_code} pentru "
                    f"{FILES_SERVICE_NAME}"
                )
                return None
            instances = response.json()
            if not instances:
                logger.warning(f"Nicio instanta vie de {FILES_SERVICE_NAME}")
                return None
            return instances[0]["url"]
    except Exception as e:
        logger.warning(f"Nu am putut rezolva {FILES_SERVICE_NAME}: {e}")
        return None


async def retrieve_context(
    authorization: str,
    conversation_id: UUID,
    query: str,
    top_k: int = 4,
) -> list[dict]:
    """
    Cere fragmente relevante de la Files Service pentru ultima intrebare.

    Parametri:
      authorization   — valoarea bruta a header-ului Authorization din
                        request-ul venit la Chat Service ("Bearer <jwt>").
                        O forwardam ca atare; Files Service verifica acelasi
                        JWT (defense in depth) si filtreaza pe user_id.
      conversation_id — pentru ce conversatie cautam fisiere.
      query           — textul de cautat (ultimul mesaj user).
      top_k           — cate fragmente cerem.

    Returneaza lista de dict-uri {content, file_name, chunk_index, score}.
    La ORICE esec returneaza [] (best-effort).
    """
    url = await _resolve_files_url()
    if url is None:
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{url.rstrip('/')}/conversations/{conversation_id}/retrieve",
                headers={"Authorization": authorization},
                json={"query": query, "top_k": top_k},
            )
            if response.status_code != 200:
                logger.warning(f"Files retrieve a raspuns {response.status_code}")
                return []
            chunks = response.json().get("chunks", [])
            logger.info(
                f"RAG: am primit {len(chunks)} fragmente pentru conv {conversation_id}"
            )
            return chunks
    except Exception as e:
        logger.warning(f"Files retrieve a esuat: {e}")
        return []
