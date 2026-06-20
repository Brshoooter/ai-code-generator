"""
Client HTTP catre Files Service pentru cleanup-ul cascade la stergerea unei
conversatii.

Cand utilizatorul sterge o conversatie, History sterge mesajele din DB-ul
propriu si apoi cere Files Service sa stearga fisierele asociate (binare din
S3 + randuri din DB). History coordoneaza, Files executa.

De ce un fisier separat (acelasi rationament ca la Chat Service):
  - Izolam rezolvarea URL-ului prin Service Discovery si apelul HTTP.
  - history_service.py ramane curat, fara dependinte de retea.

Best-effort: ORICE esec (Service Discovery cazut, files-service indisponibil,
non-200, timeout) e doar logat ca warning. Stergerea conversatiei a reusit
deja in DB-ul History; un Files Service jos nu trebuie sa o anuleze. La nevoie,
fisierele orfane pot fi curatate ulterior (vezi lifecycle rule din plan).
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
    acelasi endpoint folosit de discovery_client din Gateway. Luam prima
    instanta (fara round-robin — in dev un singur container). Returneaza None
    daca SD e cazut sau nu exista instante vii.
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


async def delete_conversation_files(user_id: str, conversation_id: UUID) -> None:
    """
    Cere Files Service sa stearga toate fisierele unei conversatii.

    Ruta interna nu foloseste JWT — trimitem header-ul X-Internal-Service
    (bariera ca ruta sa nu fie apelata din afara fluxului intern) si user_id
    explicit in body. Files Service e idempotent: daca nu sunt fisiere,
    raspunde 0 fara eroare.

    Best-effort: nu ridica exceptii. Stergerea conversatiei in DB-ul History
    s-a facut deja; aici doar incercam cleanup-ul fisierelor.
    """
    url = await _resolve_files_url()
    if url is None:
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                "DELETE",
                f"{url.rstrip('/')}/internal/conversations/{conversation_id}",
                headers={"X-Internal-Service": "history-service"},
                json={"user_id": user_id},
            )
            if response.status_code != 200:
                logger.warning(
                    f"Files cleanup a raspuns {response.status_code} pentru "
                    f"conv {conversation_id}"
                )
                return
            deleted = response.json().get("deleted_files", "?")
            logger.info(
                f"Files cleanup: sterse {deleted} fisiere pentru conv {conversation_id}"
            )
    except Exception as e:
        logger.warning(f"Files cleanup a esuat pentru conv {conversation_id}: {e}")
