"""
Verificari pre-upload pentru fisiere.

Scop: refuzam un upload INAINTE sa scriem ceva pe disk/S3 sau in DB.
Daca lasam validarile la final, am putea salva un fisier de 5 MB ca apoi
sa-l respingem — risipa de IO si bandwidth.

Apelat de: routes/files_controller.py la POST /conversations/{id}/files,
inainte de a citi continutul fisierului din UploadFile.

Cele 3 verificari:
  1. MIME type — strict allowlist din settings.allowed_mime (CSV).
     Refuzam executabile, imagini, etc., chiar daca extensia ar parea ok.
  2. Numar fisiere in conversatia curenta — max settings.max_files_per_conversation
     (default 5). Limita per-conversatie ca sa nu se incarce contextul RAG.
  3. Total bytes pe user — SUM(size_bytes) WHERE user_id, comparat cu
     settings.max_total_bytes_per_user (default 50 MB). Pl  afon global
     ca sa nu sara de free tier S3.

Toate erorile devin HTTPException cu status code semantic (415 / 409),
ca FastAPI sa serializeze automat raspunsul.
"""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from models.file_model import FileRecord


def _allowed_mime_set() -> set[str]:
    # parsam CSV-ul din settings o singura data per apel; e ieftin si
    # evita sa tinem o constanta globala care ar fi greu de reincarcat
    # daca se schimba env var-ul la runtime (in teste, de ex.)
    return {m.strip() for m in settings.allowed_mime.split(",") if m.strip()}


def check_mime(mime_type: str) -> None:
    """Refuza tipuri MIME care nu sunt in allowlist. 415 Unsupported Media Type."""
    if mime_type not in _allowed_mime_set():
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tip fisier nepermis: {mime_type}",
        )


def check_can_upload(
    db: Session,
    user_id: str,
    conversation_id: str,
    incoming_size: int,
    mime_type: str,
) -> None:
    """
    Ruleaza toate validarile pre-upload. Daca trece, returneaza None;
    altfel ridica HTTPException cu status code potrivit (415 sau 409).

    Parametri:
      db              — sesiunea SQLAlchemy injectata prin Depends(get_db)
      user_id         — claim 'sub' din JWT (vine din get_current_user_id)
      conversation_id — UUID-ul conversatiei (din path param)
      incoming_size   — Content-Length al fisierului (bytes)
      mime_type       — Content-Type declarat de browser
    """
    # 1. MIME — verificat primul, e cel mai ieftin (nu atinge DB)
    check_mime(mime_type)

    # 2. Limita per-fisier — verificare suplimentara fata de header-ul HTTP,
    #    in caz ca clientul a mintit despre Content-Length (rar, dar posibil)
    if incoming_size > settings.max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fisier prea mare: {incoming_size} > {settings.max_file_bytes} bytes",
        )

    # 3. Numar fisiere in conversatie — COUNT(*) WHERE user_id si conv_id.
    #    Filtram dupa user_id desi conv_id ar fi suficient: defense-in-depth,
    #    daca cumva exista coliziune de UUID (teoretic 0, dar costa nimic).
    files_in_conv = (
        db.query(func.count(FileRecord.id))
        .filter(
            FileRecord.user_id == user_id,
            FileRecord.conversation_id == conversation_id,
        )
        .scalar()
    )
    if files_in_conv >= settings.max_files_per_conversation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Limita de {settings.max_files_per_conversation} fisiere "
                f"per conversatie atinsa"
            ),
        )

    # 4. Total bytes per user — SUM(size_bytes) WHERE user_id.
    #    SUM peste 0 randuri intoarce NULL in SQL standard; COALESCE-l la 0
    #    ca sa pot aduna incoming_size direct fara branch in Python.
    total_bytes = (
        db.query(func.coalesce(func.sum(FileRecord.size_bytes), 0))
        .filter(FileRecord.user_id == user_id)
        .scalar()
    )
    if total_bytes + incoming_size > settings.max_total_bytes_per_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cota totala depasita: {total_bytes + incoming_size} > "
                f"{settings.max_total_bytes_per_user} bytes"
            ),
        )
