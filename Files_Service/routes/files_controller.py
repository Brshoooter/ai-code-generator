"""
Controller HTTP pentru fisiere — strat subtire intre FastAPI si services/.

In conventia MVC din proiect, route-urile NU contin logica de business:
  - parseaza input-ul (path params, JWT, UploadFile)
  - cheama functii din services/
  - returneaza un model Pydantic

In Etapa 2 endpointurile salveaza doar metadata in tabela "files" si
fisierul brut in S3 (stub). Coloana de chunks ramane goala —
embedding-ul vine in Etapa 3, prin rag_service.

Endpointuri:
  POST   /conversations/{conv_id}/files   → upload (returneaza FileResponse)
  GET    /conversations/{conv_id}/files   → lista fisiere user pe conversatie
  DELETE /files/{file_id}                 → sterge fisier (404 daca nu e al userului)
  GET    /files/{file_id}/download        → descarca / previzualizeaza binarul
"""

import logging
import re
import uuid
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from config import settings
from database.database import get_db
from models.file_model import FileRecord
from models.schemas import FileListItem, FileResponse
from services import quota_service, rag_service
from services.jwt_handler import get_current_user_id
from services.s3_client import S3Client

logger = logging.getLogger(__name__)
router = APIRouter()

# Un singur S3Client pe instanta de proces — clientul boto3 e thread-safe
# si reutilizabil; in mod stub doar tine path-ul si creeaza directoarele.
s3_client = S3Client(settings)


def _safe_filename(name: str) -> str:
    """
    Curata numele original al fisierului inainte sa-l punem in S3 key.
    Pastram doar litere, cifre, punct, liniuta si underscore — orice
    altceva (spatii, slash-uri, caractere unicode exotice) devine "_".

    De ce: S3 key-urile pot contine slash-uri, dar acelea sunt interpretate
    ca prefixe (foldere virtuale). Daca un user incarca "../../etc/passwd"
    sau "my file.pdf", vrem sa controlam noi forma key-ului.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file"


# ─────────────────────────────────────────────────────────────────
# POST /conversations/{conv_id}/files — upload
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/conversations/{conv_id}/files",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    conv_id: UUID,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Upload fisier intr-o conversatie. Pasi:
      1. Citim continutul (cap 5 MB — limita aplicata de quota_service)
      2. Validam: MIME, marime, nr fisiere/conv, total bytes/user
      3. Generam file_id si s3_key in formatul "user_id/conv_id/{file_id}-{nume}"
      4. Salvam binarul in S3 (sau stub local)
      5. Insert in tabela "files" cu chunks=0 (fara embedding in Etapa 2)
      6. Daca insert-ul DB pica, stergem obiectul S3 ca sa nu ramana orfan

    NU citim tot in memorie inainte de validari — Content-Length header
    ne lasa sa respingem un fisier prea mare fara sa-l descarcam.
    """
    # MIME-ul vine din Content-Type al partii multipart; FastAPI il pune
    # pe upload_file.content_type. Daca lipseste, refuzam clar in loc sa
    # ghicim dupa extensie.
    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content-Type lipseste in upload",
        )

    # Citim continutul integral. Limita de 5 MB e aplicata de quota_service
    # imediat dupa, deci nu risc OOM (FastAPI inca nu mi-a parsat tot daca
    # excede max_request_size la nivel de server, dar in dev-ul nostru e ok).
    content = await file.read()
    incoming_size = len(content)

    # Toate validarile intr-un singur loc — daca pica, ridica HTTPException
    quota_service.check_can_upload(
        db=db,
        user_id=user_id,
        conversation_id=str(conv_id),
        incoming_size=incoming_size,
        mime_type=file.content_type,
    )

    # Construim identitatea fisierului si key-ul S3
    file_id = uuid.uuid4()
    safe_name = _safe_filename(file.filename or "file")
    s3_key = f"{user_id}/{conv_id}/{file_id}-{safe_name}"

    # Salvare binara — daca pica, n-am scris nimic in DB inca, deci nimic
    # de revenit. Lasa exceptia sa propage → 500 din partea FastAPI.
    s3_client.put_object(s3_key, content, file.content_type)

    # Insert metadata + chunks intr-o singura tranzactie atomica:
    #   add(FileRecord) → flush → embed_and_store_chunks(...) → commit
    # Daca orice pas pica, db.rollback() anuleaza ambele insert-uri
    # si stergem obiectul S3 ca sa nu ramana orfan.
    record = FileRecord(
        id=file_id,
        user_id=user_id,
        conversation_id=conv_id,
        s3_key=s3_key,
        original_name=file.filename or safe_name,
        mime_type=file.content_type,
        size_bytes=incoming_size,
        status="ready",
    )
    chunks_count = 0
    try:
        db.add(record)
        # flush() emite INSERT pe "files" fara sa comita tranzactia.
        # Necesar pentru ca file_chunks.file_id are FK catre files.id —
        # daca am sari direct la insert pe chunks, Postgres ar refuza FK-ul
        # pentru ca parintele nu e inca in tabel.
        db.flush()

        # Extragere text → chunking → embeddings → bulk insert in
        # file_chunks (tot in aceeasi sesiune, fara commit). Vezi rag_service.
        chunks_count = await rag_service.embed_and_store_chunks(
            db=db,
            file_id=file_id,
            content=content,
            mime_type=file.content_type,
            original_name=file.filename or safe_name,
        )

        # Commit atomic: FileRecord + N FileChunk-uri devin durabile impreuna.
        db.commit()
        db.refresh(record)
    except Exception as e:
        db.rollback()
        # rollback la S3 — best-effort, nu suprascrie eroarea originala
        try:
            s3_client.delete_object(s3_key)
        except Exception as cleanup_err:
            logger.warning(f"Cleanup S3 esuat dupa rollback DB: {cleanup_err}")
        logger.exception(f"Ingest esuat pentru {safe_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Procesare fisier esuata: {e}",
        )

    # FileResponse asteapta "file_id", dar coloana SQL se cheama "id".
    # Construim manual ca sa fim explicit; from_attributes nu mapeaza id→file_id.
    return FileResponse(
        file_id=record.id,
        original_name=record.original_name,
        size_bytes=record.size_bytes,
        mime_type=record.mime_type,
        chunks=chunks_count,
        status=record.status,
        created_at=record.created_at,
    )


# ─────────────────────────────────────────────────────────────────
# GET /conversations/{conv_id}/files — lista
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/conversations/{conv_id}/files",
    response_model=list[FileListItem],
)
def list_files(
    conv_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returneaza fisierele din conversatie pentru userul curent.

    Filtrare dupa user_id + conversation_id — un user nu poate vedea
    fisierele altcuiva nici daca ghiceste un conv_id valid (varianta
    "trust-on-JWT + WHERE user_id" din planul de arhitectura).
    """
    rows = (
        db.query(FileRecord)
        .filter(
            FileRecord.user_id == user_id,
            FileRecord.conversation_id == conv_id,
        )
        .order_by(FileRecord.created_at.asc())
        .all()
    )
    # FileListItem foloseste from_attributes pentru a citi din ORM, dar
    # cere campul "file_id", nu "id" — construim explicit.
    return [
        FileListItem(
            file_id=r.id,
            original_name=r.original_name,
            size_bytes=r.size_bytes,
            mime_type=r.mime_type,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────
# DELETE /files/{file_id} — sterge un fisier
# ─────────────────────────────────────────────────────────────────
@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_file(
    file_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Sterge fisierul si obiectul S3 asociat.

    Daca fisierul nu exista SAU apartine altui user → 404 (nu 403).
    De ce 404: 403 ar confirma existenta ID-ului → atacatorul afla ca
    UUID-ul e valid, doar nu apartine lui. 404 spune doar "nu exista
    pentru tine" si nu leak-uieste informatie despre alti useri
    (acelasi pattern ca in History Service).

    Cascade-ul pe chunks e setat in modelul SQLAlchemy (ondelete=CASCADE
    + relationship cascade), deci stergerea unui FileRecord sterge automat
    si randurile din file_chunks.
    """
    record = (
        db.query(FileRecord)
        .filter(
            FileRecord.id == file_id,
            FileRecord.user_id == user_id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fisier inexistent",
        )

    # Stergem intai din S3, apoi din DB. Daca S3 pica, abandonam — fisierul
    # ramane in DB si la urmatorul retry incercam iar. Daca facem invers,
    # un esec S3 ar lasa obiectul orfan fara metadata pentru cleanup.
    try:
        s3_client.delete_object(record.s3_key)
    except Exception as e:
        logger.warning(f"Stergere S3 esuata pentru {record.s3_key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Eroare la stergerea binarului",
        )

    db.delete(record)
    db.commit()
    # 204 No Content — nu returnam body
    return None


# ─────────────────────────────────────────────────────────────────
# GET /files/{file_id}/download — descarca / previzualizeaza
# ─────────────────────────────────────────────────────────────────
@router.get("/files/{file_id}/download")
def download_file(
    file_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returneaza binarul fisierului pentru afisare/descarcare in browser.

    Auth: JWT obligatoriu; ownership verificat prin WHERE user_id = :sub.
    Daca fisierul nu exista SAU apartine altui user → 404 (acelasi pattern
    anti-enumeration ca la delete).

    Construim manual un Response (fara response_model) pentru ca raspunsul
    nu e JSON, ci bytes brute cu Content-Type specific (PDF/text/etc).

    Header-ul Content-Disposition: inline cere browser-ului sa randeze
    direct in tab tipurile pe care le stie (PDF, text, imagini); pentru
    restul (ex. .docx) browser-ul cade automat pe descarcare.
    """
    record = (
        db.query(FileRecord)
        .filter(
            FileRecord.id == file_id,
            FileRecord.user_id == user_id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fisier inexistent",
        )

    # Citim binarul din S3 (sau stub local). Daca obiectul lipseste fizic
    # desi metadata exista, e o inconsistenta serioasa — log + 500.
    try:
        body = s3_client.get_object(record.s3_key)
    except FileNotFoundError:
        logger.error(
            f"Inconsistenta: row exista pentru file_id={file_id} dar "
            f"obiectul S3 {record.s3_key} lipseste"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binarul fisierului nu a fost gasit",
        )
    except Exception as e:
        logger.exception(f"Citire S3 esuata pentru {record.s3_key}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Eroare la citirea binarului: {e}",
        )

    # filename intre ghilimele duble — daca numele contine spatii sau
    # caractere speciale, browser-ul il interpreteaza corect.
    safe_name = record.original_name.replace('"', "")
    return Response(
        content=body,
        media_type=record.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Content-Length": str(len(body)),
        },
    )
