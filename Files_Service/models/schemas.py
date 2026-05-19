from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Schemas pentru endpointurile publice (apelate prin Gateway cu JWT)
# ─────────────────────────────────────────────────────────────────

# Raspuns dupa upload reusit. "chunks" e numarul de bucati salvate dupa
# extragere si splitting (in Etapa 2 va fi mereu 0; in Etapa 3 va creste).
class FileResponse(BaseModel):
    file_id: UUID
    original_name: str
    size_bytes: int
    mime_type: str
    chunks: int
    status: str
    created_at: datetime

    # Pydantic v2: permite construirea direct din obiecte SQLAlchemy
    # (acceseaza atributele in loc sa astepte dict). Inlocuieste vechiul
    # orm_mode = True din Pydantic v1.
    model_config = {"from_attributes": True}


# Raspuns pentru GET /conversations/{id}/files — fara "chunks" si "status",
# nu sunt utile pentru afisare in UI.
class FileListItem(BaseModel):
    file_id: UUID
    original_name: str
    size_bytes: int
    mime_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# Body pentru POST /conversations/{id}/retrieve — apelat de Chat Service
# cu JWT-ul utilizatorului forwardat.
# Field(...) ne lasa sa adaugam validari direct in tip; min_length=1 inseamna
# ca nu acceptam query gol, max_length=4000 evita query-uri patologice.
class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=20)


# Un singur chunk returnat la retrieval. "score" = 1 - distanta cosine,
# deci e in [-1, 1]; mai mare = mai similar. Util pentru log/debug, nu
# pentru filtering hard (tinem mereu top_k).
class ChunkOut(BaseModel):
    content: str
    file_name: str
    chunk_index: int
    score: float


class RetrieveResponse(BaseModel):
    chunks: list[ChunkOut]


# ─────────────────────────────────────────────────────────────────
# Schemas pentru endpointul intern (DELETE /internal/conversations/{id})
# ─────────────────────────────────────────────────────────────────
# Ruta interna NU foloseste JWT — History Service trimite explicit user_id
# si un header X-Internal-Service. Vom verifica header-ul in routes/.
class InternalDeleteRequest(BaseModel):
    user_id: str


class InternalDeleteResponse(BaseModel):
    deleted_files: int
