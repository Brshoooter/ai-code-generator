# Plan de implementare: Files_Service (RAG + S3)

> Document de instructiuni pentru un agent care va implementa microserviciul. Citeste integral inainte de a scrie cod. Limba: romana fara diacritice (conform CLAUDE.md). Stil: pedagogic — explica utilizatorului fiecare concept nou inainte de a-l folosi.

## 0. Context obligatoriu de citit

Inainte sa scrii orice linie de cod, citeste:
- `CLAUDE.md` (radacina) — sectiunile **Teaching Mode**, **Architecture**, **Service Structure Convention**, **Key Patterns**, **Language & Style**.
- `Authentication_Service/` — ca referinta pentru structura MVC.
- `History_Service/` — referinta pentru: defense-in-depth JWT, ownership 404 (nu 403), `lifespan` cu register/deregister la Service Discovery, schema SQLAlchemy + `Base.metadata.create_all` la startup.
- `Chat_Service/` — pentru cum se cheama Ollama prin `langchain-ollama` si pentru fluxul de streaming care va fi modificat.
- `API_Gateway/services/proxy_service.py` si `routes/` — sa intelegi cum trec request-urile catre servicii noi.
- `docker-compose.yml` — pentru pattern-ul de adaugare serviciu + Postgres dedicat.

**Reguli stricte de stil**:
- Toate comentariile in cod si textele de log — in romana fara diacritice (`a` nu `a`, `s` nu `s`, `t` nu `t`).
- Conventie MVC stricta: `routes/` (subtire, doar HTTP), `services/` (logica), `models/` (SQLAlchemy + Pydantic), `database/` (engine + session).
- Nu adauga features dincolo de plan. Nu inventa endpoints. Daca ceva nu e specificat, intreaba inainte sa codezi.

## 1. Decizii de arhitectura (deja luate, nu le rediscuta)

| Decizie | Valoare | Motivatie |
|---|---|---|
| Vector store | **pgvector** intr-un Postgres dedicat (`postgres-files`) | Coerenta cu pattern-ul "un Postgres per serviciu" din auth si history |
| Embedding model | **`nomic-embed-text`** (768 dim) prin **Ollama local** | Gratis, ruleaza pe acelasi Ollama ca codellama, 0 cost AWS |
| Scope fisiere | **per conversatie** | Stergerea in cascade e simpla; userul re-upload-eaza in conversatie noua |
| Upload pattern | **proxy prin backend** (frontend → Gateway → Files → S3) | Mai simplu de aratat la prezentare; pre-signed URL e imbunatatire viitoare |
| Procesare | **sincron** (user asteapta pana embeddings sunt gata) | Fisiere mici (≤5 MB); nu merita state machine de `processing` |
| Orchestrare RAG | **Chat Service cheama Files Service** (varianta b) | Frontend ramane aproape neatins; Chat Service stie sa-si imbogateasca prompt-ul |
| Ownership check | **trust-on-JWT + filtrare la SELECT** (varianta c) | `WHERE user_id = :sub` izoleaza datele; fara coupling intre servicii |
| Stergere cascade | **History → Files** prin endpoint intern la stergerea conversatiei | History coordoneaza stergerea; Files executa |
| Limite | 5 MB/fisier, 5 fisiere/conversatie, 50 MB total/utilizator | Strict ca sa nu sara de free tier S3 |
| Tipuri permise | PDF, TXT, MD, .py, .js, .ts, .c, .cpp, .java, .go, .rs | Cod + documentatie text |
| AWS region | `eu-central-1` (Frankfurt) | Latenta minima |
| Bucket | unul singur, prefixe `user_id/conversation_id/file_id-name.ext` | Mai usor de administrat decat 1 bucket per user |

## 2. Structura folderului

```
Files_Service/
  main.py
  config.py
  Dockerfile
  requirements.txt
  routes/
    __init__.py
    files_routes.py
  services/
    __init__.py
    sd_client.py
    jwt_handler.py
    s3_client.py
    text_extractor.py
    chunker.py
    embedder.py
    rag_service.py
    quota_service.py
  models/
    __init__.py
    file_model.py
    schemas.py
  database/
    __init__.py
    db.py
  keys/
    .gitkeep              # public.pem se pune manual, e gitignored
```

## 3. Configuratie (`config.py`)

Pydantic `BaseSettings` cu prefix `FILES_`:

```python
class Settings(BaseSettings):
    # Server
    port: int = 8003

    # Service Discovery
    sd_url: str = "http://service-discovery:8500"
    service_url: str = "http://files-service:8003"
    service_name: str = "files-service"

    # Database
    database_url: str = "postgresql+psycopg2://files_user:files_pass@postgres-files:5432/files_db"

    # JWT (defense in depth)
    jwt_public_key_path: str = "keys/public.pem"
    jwt_algorithm: str = "RS256"

    # Ollama embeddings
    ollama_base_url: str = "http://host.docker.internal:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 100

    # Limite
    max_file_bytes: int = 5 * 1024 * 1024           # 5 MB
    max_files_per_conversation: int = 5
    max_total_bytes_per_user: int = 50 * 1024 * 1024  # 50 MB

    # Retrieval
    retrieve_top_k: int = 4

    # MIME allowlist (string CSV pentru env, parse in cod)
    allowed_mime: str = (
        "application/pdf,"
        "text/plain,"
        "text/markdown,"
        "text/x-python,"
        "application/javascript,"
        "application/x-typescript,"
        "text/x-c,"
        "text/x-c++,"
        "text/x-java-source,"
        "text/x-go,"
        "text/x-rust"
    )

    # AWS S3 (gol la inceput → mod stub local)
    aws_region: str = "eu-central-1"
    s3_bucket: str = ""           # gol = stub local
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_local_stub_dir: str = "/tmp/local-files-bucket"

    class Config:
        env_prefix = "FILES_"
        env_file = ".env"
```

## 4. Schema bazei de date

Postgres image: **`pgvector/pgvector:pg16`** (are extensia preinstalata).

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE files (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         TEXT NOT NULL,
  conversation_id UUID NOT NULL,
  s3_key          TEXT NOT NULL UNIQUE,
  original_name   TEXT NOT NULL,
  mime_type       TEXT NOT NULL,
  size_bytes      INT  NOT NULL,
  status          TEXT NOT NULL DEFAULT 'ready',
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_files_user_conv ON files(user_id, conversation_id);
CREATE INDEX ix_files_user      ON files(user_id);

CREATE TABLE file_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  file_id     UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_index INT  NOT NULL,
  content     TEXT NOT NULL,
  embedding   VECTOR(768) NOT NULL
);
CREATE INDEX ix_chunks_embedding ON file_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ix_chunks_file ON file_chunks(file_id);
```

**SQLAlchemy** (in `models/file_model.py`):
- `from pgvector.sqlalchemy import Vector` — tip de coloana din pachetul `pgvector`.
- `embedding = Column(Vector(768), nullable=False)`.
- `Base.metadata.create_all(engine)` la lifespan **dupa** ce ai rulat manual `CREATE EXTENSION IF NOT EXISTS vector;` (extensia trebuie inainte de `CREATE TABLE` cu `Vector`).

**Lifespan startup** (in `main.py`):
1. Conexiune DB → exec `CREATE EXTENSION IF NOT EXISTS vector`.
2. `Base.metadata.create_all(engine)`.
3. Verifica directorul stub S3 daca `s3_bucket == ""`.
4. Inregistreaza la Service Discovery (`sd_client.register`).
5. La shutdown — deregister.

## 5. Endpoints

Toate sub `/api/files-service/...` cand sunt apelate prin Gateway.

### `POST /conversations/{conv_id}/files` — upload
- Auth: JWT obligatoriu, extrage `user_id = claims["sub"]`.
- Body: `multipart/form-data` cu camp `file: UploadFile`.
- Validari (in ordinea asta, **inainte** de a citi continutul integral):
  1. MIME in `allowed_mime` → altfel 415.
  2. Header `Content-Length` ≤ `max_file_bytes` → altfel 413.
  3. Numar fisiere existente in `(user_id, conv_id)` < `max_files_per_conversation` → altfel 409.
  4. `SUM(size_bytes) WHERE user_id = :sub` + size_curent ≤ `max_total_bytes_per_user` → altfel 409.
- Flux:
  1. Genereaza `file_id = uuid4()`.
  2. `s3_key = f"{user_id}/{conv_id}/{file_id}-{safe_name}"`.
  3. Streamuieste in S3 (sau stub local).
  4. Extrage text (vezi `text_extractor`).
  5. Chunk → embed → bulk insert in `file_chunks`.
  6. Insert in `files` cu `status='ready'`.
  7. Toata operatia intr-o **tranzactie DB**; daca embedding-ul esueaza, sterge obiectul S3 si raspunde 500.
- Response 201:
  ```json
  {"file_id": "...", "original_name": "...", "size_bytes": 1234,
   "mime_type": "...", "chunks": 12, "status": "ready"}
  ```

### `GET /conversations/{conv_id}/files` — lista
- Filtreaza `WHERE user_id = :sub AND conversation_id = :conv_id`.
- Returneaza `[{file_id, original_name, size_bytes, mime_type, created_at}]`.

### `DELETE /files/{file_id}` — sterge un fisier
- `SELECT ... WHERE id = :file_id AND user_id = :sub` — daca nu exista → **404**.
- Sterge din S3, apoi `DELETE FROM files WHERE id = :file_id` (cascade pe chunks).

### `GET /files/{file_id}/download` — descarca / previzualizeaza fisierul
- Auth: JWT obligatoriu, extrage `user_id = claims["sub"]`.
- Flux:
  1. `SELECT s3_key, mime_type, original_name, size_bytes FROM files WHERE id = :file_id AND user_id = :sub` — daca nu exista → **404** (acelasi pattern ca la History pentru a nu leakui ID-uri).
  2. `s3.get_object(s3_key)` → bytes.
  3. Returneaza `Response(content=bytes, media_type=mime_type, headers={"Content-Disposition": f'inline; filename="{original_name}"'})`.
- `inline` permite browser-ului sa randeze direct PDF/text in tab; pentru tipuri pe care nu le poate randa, browser-ul ofera automat download.
- Nu trece prin embeddings, nu modifica DB — e o operatie read-only peste S3 si o singura linie SQL.

### `POST /conversations/{conv_id}/retrieve` — retrieval pentru Chat Service
- Auth: JWT (acelasi token pe care il avea utilizatorul; Chat Service il forwardeaza).
- Body: `{"query": "...", "top_k": 4}` (top_k optional, default `retrieve_top_k`).
- Flux:
  1. Embed `query` cu acelasi model.
  2. SQL:
     ```sql
     SELECT fc.content, fc.chunk_index, f.original_name,
            (fc.embedding <=> :q) AS distance
       FROM file_chunks fc
       JOIN files f ON f.id = fc.file_id
      WHERE f.user_id = :sub
        AND f.conversation_id = :conv_id
      ORDER BY fc.embedding <=> :q
      LIMIT :top_k;
     ```
  3. Returneaza `[{content, file_name, chunk_index, score: 1 - distance}]` (cosine distance ∈ [0,2]; "score" e doar pentru afisare/log, nu critic).

### `DELETE /internal/conversations/{conv_id}` — cleanup cascade
- Header obligatoriu: `X-Internal-Service: history-service`. Daca lipseste → 403.
- Body: `{"user_id": "..."}` (History il trimite explicit; nu venim cu JWT pe ruta interna).
- Flux:
  1. `SELECT s3_key FROM files WHERE user_id = :uid AND conversation_id = :cid`.
  2. `delete_objects` in batch din S3.
  3. `DELETE FROM files WHERE user_id = :uid AND conversation_id = :cid` (cascade pe chunks).
  4. Raspunde `{"deleted_files": N}`. Idempotent — daca nu exista nimic, returneaza `0`.

### `GET /health`
- Ping DB (`SELECT 1`), verifica reachability Ollama (optional, doar warning daca pica), verifica accesibilitate S3 (`head_bucket` daca `s3_bucket != ""`).
- Raspunde `{"status": "ok", "db": "ok", "ollama": "ok|warning", "s3": "ok|stub"}`.

## 6. Module `services/`

### `sd_client.py`
Copy-paste din `History_Service/services/sd_client.py`. Schimba doar `service_name` → `"files-service"`.

### `jwt_handler.py`
Copy-paste din `History_Service/services/jwt_handler.py`. Acelasi cod (verifica RS256 cu `keys/public.pem`, raise 401 pe invalid).

### `s3_client.py`
Wrapper peste `boto3` cu **fallback la stub local** pentru dezvoltare fara cont AWS.

```python
class S3Client:
    def __init__(self, settings):
        self.use_stub = not settings.s3_bucket
        if self.use_stub:
            self.stub_dir = Path(settings.s3_local_stub_dir)
            self.stub_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.bucket = settings.s3_bucket
            self.client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

    def put_object(self, key: str, body: bytes, content_type: str): ...
    def delete_object(self, key: str): ...
    def delete_prefix(self, prefix: str) -> int: ...   # pentru cleanup conversatie
    def get_object(self, key: str) -> bytes: ...       # daca avem nevoie ulterior
```

In modul stub: scrie/citeste fisiere sub `stub_dir / key` (creeaza subdirectoare).

### `text_extractor.py`
```python
def extract_text(content: bytes, mime_type: str, original_name: str) -> str:
    if mime_type == "application/pdf":
        return _extract_pdf(content)
    # restul (text/*) → decode UTF-8 cu fallback latin-1
    return content.decode("utf-8", errors="replace")

def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
```

Daca textul rezultat e gol/sub 10 caractere (PDF scanat fara OCR), log warning si lasa `chunks=0` (fisierul ramane salvat fara embeddings).

### `chunker.py`
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split(text: str, chunk_size: int, overlap: int) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)
```

### `embedder.py`
Client HTTP catre Ollama. **Nu folosi LangChain** aici — apel direct cu `httpx`, e mai simplu si controlat.

```python
class Embedder:
    def __init__(self, base_url: str, model: str, dim: int):
        self.base_url = base_url
        self.model = model
        self.dim = dim

    async def embed_one(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            r.raise_for_status()
            vec = r.json()["embedding"]
            assert len(vec) == self.dim, f"expected {self.dim}, got {len(vec)}"
            return vec

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        # Ollama nu suporta batching in /api/embeddings → serial
        return [await self.embed_one(t) for t in texts]
```

### `rag_service.py`
Orchestratorul:
- `ingest_file(db, user_id, conv_id, upload_file) -> FileResponse` — face validari + S3 + extract + chunk + embed + insert.
- `retrieve(db, user_id, conv_id, query, top_k) -> list[ChunkOut]` — embed + SQL.
- `delete_file(db, user_id, file_id)`.
- `delete_conversation(db, user_id, conv_id) -> int`.

### `quota_service.py`
- `check_can_upload(db, user_id, conv_id, incoming_size) -> None | raises HTTPException`.
- O singura functie cu cele 3 verificari (nr. fisiere conv, total user, MIME daca e cazul).

## 7. Modele Pydantic (`models/schemas.py`)

```python
class FileResponse(BaseModel):
    file_id: UUID
    original_name: str
    size_bytes: int
    mime_type: str
    chunks: int
    status: str
    created_at: datetime

class FileListItem(BaseModel):
    file_id: UUID
    original_name: str
    size_bytes: int
    mime_type: str
    created_at: datetime

class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=20)

class ChunkOut(BaseModel):
    content: str
    file_name: str
    chunk_index: int
    score: float

class RetrieveResponse(BaseModel):
    chunks: list[ChunkOut]

class InternalDeleteRequest(BaseModel):
    user_id: str

class InternalDeleteResponse(BaseModel):
    deleted_files: int
```

## 8. `requirements.txt`

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
sqlalchemy==2.0.*
psycopg2-binary==2.9.*
pgvector==0.3.*
pydantic==2.*
pydantic-settings==2.*
httpx==0.27.*
python-multipart==0.0.*
pyjwt[crypto]==2.*
pypdf==4.*
langchain-text-splitters==0.3.*
boto3==1.35.*
```

## 9. Dockerfile

Copy-paste din `History_Service/Dockerfile`, schimba portul la `8003`.

## 10. Modificari `docker-compose.yml`

Adauga:

```yaml
postgres-files:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_DB: files_db
    POSTGRES_USER: files_user
    POSTGRES_PASSWORD: files_pass
  ports:
    - "5434:5432"
  volumes:
    - postgres-files-data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD", "pg_isready", "-U", "files_user", "-d", "files_db"]
    interval: 5s
    timeout: 5s
    retries: 10

files-service:
  build: ./Files_Service
  ports:
    - "8003:8003"
  environment:
    FILES_PORT: 8003
    FILES_SD_URL: http://service-discovery:8500
    FILES_SERVICE_URL: http://files-service:8003
    FILES_DATABASE_URL: postgresql+psycopg2://files_user:files_pass@postgres-files:5432/files_db
    FILES_OLLAMA_BASE_URL: http://host.docker.internal:11434
    FILES_S3_BUCKET: ${FILES_S3_BUCKET:-}
    FILES_AWS_REGION: ${FILES_AWS_REGION:-eu-central-1}
    FILES_AWS_ACCESS_KEY_ID: ${FILES_AWS_ACCESS_KEY_ID:-}
    FILES_AWS_SECRET_ACCESS_KEY: ${FILES_AWS_SECRET_ACCESS_KEY:-}
  depends_on:
    postgres-files:
      condition: service_healthy
    service-discovery:
      condition: service_started
  extra_hosts:
    - "host.docker.internal:host-gateway"
  volumes:
    - ./Files_Service/keys/public.pem:/app/keys/public.pem:ro

# In sectiunea volumes existenta:
volumes:
  postgres-files-data:
```

## 11. Modificari in serviciile existente

### Chat Service (`Chat_Service/`)

1. In schema request-ului din `routes/`:
   ```python
   class GenerateRequest(BaseModel):
       messages: list[Message]
       conversation_id: Optional[UUID] = None
   ```
2. In `services/` — un client nou `files_client.py`:
   ```python
   async def retrieve_context(token: str, conv_id: UUID, query: str) -> list[dict]:
       url = await sd_client.get_url("files-service")
       async with httpx.AsyncClient(timeout=10.0) as c:
           r = await c.post(
               f"{url}/conversations/{conv_id}/retrieve",
               headers={"Authorization": f"Bearer {token}"},
               json={"query": query, "top_k": 4},
           )
           if r.status_code != 200:
               return []   # best-effort
           return r.json()["chunks"]
   ```
3. In handler-ul de generate:
   - Daca `conversation_id` e setat si exista mesaje user, ia ultimul `role="user"` ca `query`.
   - Apel `retrieve_context(token, conv_id, query)`.
   - Daca returneaza chunks: construieste un al doilea `SystemMessage` dupa cel fix:
     ```
     "Foloseste urmatorul context din fisierele utilizatorului pentru a raspunde:
     
     [Sursa: nume_fisier.py, fragment 3]
     <continut chunk 1>
     ---
     [Sursa: ...]
     <continut chunk 2>
     ..."
     ```
   - **Niciodata** nu lasa frontend-ul sa controleze SystemMessage-ul.
4. Forwardeaza header-ul `Authorization` din request-ul venit la Chat Service catre Files Service. (Adauga in routes-ul de generate parametrul `request: Request` si extrage `request.headers.get("authorization")`.)

### History Service (`History_Service/`)

1. La `DELETE /conversations/{id}`, **dupa** stergerea reusita din DB-ul propriu:
   ```python
   # best-effort: cleanup fisiere asociate
   try:
       url = await sd_client.get_url("files-service")
       async with httpx.AsyncClient(timeout=15.0) as c:
           await c.request(
               "DELETE",
               f"{url}/internal/conversations/{conv_id}",
               headers={"X-Internal-Service": "history-service"},
               json={"user_id": user_id},
           )
   except Exception as e:
       logger.warning(f"Files cleanup failed for conv {conv_id}: {e}")
   ```

### API Gateway (`API_Gateway/`)

- Niciun cod nou. Files-service e auto-rezolvat prin Service Discovery.
- Verifica **doar** ca middleware-ul nu blocheaza upload-uri `multipart/form-data` mari (5 MB). Daca exista vreo limita explicita pe `Content-Length`, ridica-o la cel putin 6 MB.

### Frontend (`code-gen-frontend/`)

Modificari **strict minime**. NU rescrie componente intregi.

1. **`src/services/conversationService.js`** — adauga 3 functii la sfarsit:
   ```javascript
   export const uploadFile = async (conversationId, file) => {
     const formData = new FormData();
     formData.append("file", file);
     return apiClient.post(
       `/api/files-service/conversations/${conversationId}/files`,
       formData,
       { headers: { "Content-Type": "multipart/form-data" } },
     );
   };
   export const listFiles = (conversationId) =>
     apiClient.get(`/api/files-service/conversations/${conversationId}/files`);
   export const deleteFile = (fileId) =>
     apiClient.delete(`/api/files-service/files/${fileId}`);
   export const downloadFile = async (fileId) => {
     // Folosim fetch + blob in loc de window.open pentru ca nu putem
     // seta header-ul Authorization pe o navigare directa de browser.
     const res = await apiClient.get(
       `/api/files-service/files/${fileId}/download`,
       { responseType: "blob" },
     );
     const url = URL.createObjectURL(res.data);
     window.open(url, "_blank");
     // Eliberam URL-ul dupa ce browser-ul a apucat sa-l deschida.
     setTimeout(() => URL.revokeObjectURL(url), 60_000);
   };
   ```

2. **`src/services/generateService.js`** — adauga `conversation_id` in body:
   ```javascript
   body: JSON.stringify({
     messages: messages.slice(-20),
     conversation_id: conversationId,   // <-- nou
   })
   ```

3. **In componenta de chat** (cea care contine input-ul):
   - Buton "Attach" (un `<label htmlFor>` pe `<input type="file" hidden>`) cu `accept=".pdf,.txt,.md,.py,.js,.ts,.c,.cpp,.java,.go,.rs"`.
   - State `attachedFiles: []` populat cu `listFiles` la deschiderea conversatiei.
   - Pe schimbarea fisierului: cheama `uploadFile`, apoi reincarca `listFiles`.
   - Afiseaza chip-uri (nume + buton X) sub input. X cheama `deleteFile`.
   - Click pe corpul chip-ului (nu pe X) cheama `downloadFile(file_id)` → previzualizare/download in tab nou.
   - **Nu** schimba logica de streaming.

## 12. Plan de executie pe etape

Implementeaza **strict in ordinea asta**, testand la fiecare pas. NU sari la urmatoarea etapa pana nu confirmi cu utilizatorul ca etapa curenta merge.

### Etapa 1 — Schelet
- Creeaza `Files_Service/` cu structura de folder.
- `main.py` cu FastAPI app + lifespan + `/health`.
- `config.py`, `database/db.py`, modele goale.
- `Dockerfile`, `requirements.txt`.
- Adauga `postgres-files` + `files-service` in `docker-compose.yml`.
- Test: `docker compose up --build`. Verifica `curl http://localhost:8003/health` si ca apare la `http://localhost:8500/services`.
- **OPRESTE-TE. Cere confirmare.**

### Etapa 2 — Schema DB + S3 stub + JWT + endpointurile fara embedding
- `CREATE EXTENSION` la lifespan.
- Modele SQLAlchemy + Pydantic.
- `s3_client.py` doar mod stub (fara boto3 real).
- `jwt_handler.py` (copy din History).
- Endpointuri `POST /conversations/{id}/files`, `GET`, `DELETE`, `GET /files/{file_id}/download` — dar **fara** embedding (lasa lista de chunks goala, scrie doar in `files`). Download-ul nu depinde de embeddings, deci se implementeaza tot aici.
- `text_extractor.py` + `chunker.py` (functioneaza, dar inca nu-l folosesti la insert chunks).
- **OPRESTE-TE. Test cu curl + verificare in DB. Cere confirmare.**

### Etapa 3 — Embeddings prin Ollama
- Asigura-te ca utilizatorul a rulat `ollama pull nomic-embed-text`.
- `embedder.py` cu apel real la Ollama.
- Integreaza in `rag_service.ingest_file`: dupa chunking, fa embed, insert in `file_chunks`.
- Endpoint `POST /conversations/{id}/retrieve`.
- **OPRESTE-TE. Test: upload README.md, apel manual `/retrieve` cu un query relevant, verifica chunks returnate. Cere confirmare.**

### Etapa 4 — Integrare Chat Service
- Modifica Chat Service conform sectiunii 11.
- **OPRESTE-TE. Test end-to-end: upload fisier .py cu o functie, intreaba in chat "ce face functia X". Verifica ca raspunsul foloseste continutul. Cere confirmare.**

### Etapa 5 — Cascade din History
- Endpoint `DELETE /internal/conversations/{id}` in Files.
- Modificare in History conform sectiunii 11.
- **OPRESTE-TE. Test: upload fisier, sterge conversatia, verifica ca row-urile + obiectele stub au disparut. Cere confirmare.**

### Etapa 6 — Frontend
- Modificari minime in `conversationService`, `generateService`, componenta chat.
- Pornire dev server, test in browser cu fluxul complet.
- **OPRESTE-TE. Cere confirmare.**

### Etapa 7 — Migrare AWS S3 (DUPA ce utilizatorul are cont AWS)
**Pasi de pregatire pe care utilizatorul ii face manual** (nu-i automatiza):
1. Cont AWS nou + activare MFA pe root.
2. **Billing alerts**: `$1`, `$5`, `$10` (CloudWatch / Budgets) — **inainte** de orice altceva.
3. IAM user dedicat `files-service-user` cu policy minimal:
   ```json
   {"Version":"2012-10-17","Statement":[{
     "Effect":"Allow",
     "Action":["s3:PutObject","s3:GetObject","s3:DeleteObject","s3:ListBucket"],
     "Resource":["arn:aws:s3:::BUCKET_NAME","arn:aws:s3:::BUCKET_NAME/*"]
   }]}
   ```
4. Bucket `globalproject-licenta-files-<random>` in `eu-central-1`, **Block all public access ON**, versioning OFF.
5. Lifecycle rule: stergere obiecte mai vechi de 7 zile cu tag `orphan` (safety net pentru viitor; momentan optional).

**Modificari in cod**:
- Doar in `s3_client.py` — branch-ul `boto3` exista deja. Activarea se face setand `FILES_S3_BUCKET` in `.env`.
- `.env` (gitignored, NU il commit-a).
- Test: upload, verifica obiectul in consola S3, sterge conversatia, verifica disparitia.

## 13. Reguli de comunicare cu utilizatorul (pedagogie)

- Inainte de fiecare etapa: scrie 2-3 propozitii despre **ce** vei face si **de ce**.
- La fiecare concept nou folosit (pgvector, `ivfflat`, `RecursiveCharacterTextSplitter`, `multipart/form-data`, lifecycle policy etc.): explica scurt ce e si ce face in contextul nostru.
- La final de etapa: rezumat scurt — ce s-a modificat, ce trebuie testat manual, ce concept nou ar trebui sa retina.
- NU continua la etapa urmatoare fara "OK" explicit de la utilizator.

## 14. Lista riscuri cunoscute

- **Ollama nu are `nomic-embed-text`** → la lifespan, log warning daca lipseste din `/api/tags`.
- **PDF scanat (imagini)** → text gol, fisierul ramane in S3 cu `chunks=0`. Log warning, raspuns clar la user.
- **Race condition pe quota** la upload-uri paralele de la acelasi user → acceptabil pentru licenta. Mentioneaza-l in raspunsul final ca limitare cunoscuta.
- **CPU slab → embeddings lente** → daca depaseste 30s, creste `chunk_size` la 1200.
- **Gateway timeout pe upload mare** → verifica configul httpx in `proxy_service.py`; daca timeout < 60s, mareste-l pentru ruta de upload.

## 15. Definition of Done

- `docker compose up --build` porneste tot stack-ul fara erori.
- Health checks verzi pentru `files-service` si `postgres-files`.
- `files-service` apare in registry-ul Service Discovery.
- Upload, list, delete fisier functioneaza prin Gateway cu JWT.
- `/retrieve` returneaza chunks ordonate dupa similaritate.
- Chat Service injecteaza context si raspunsul reflecta continutul fisierului.
- Stergere conversatie din History → fisierele dispar din DB-ul Files si din S3 (sau stub).
- Frontend: buton attach functioneaza, lista fisiere se afiseaza, delete merge, click pe chip deschide previzualizarea fisierului in tab nou.
- Toate comentariile in romana fara diacritice.
- Niciun fisier `.pem` sau `.env` nu e commit-uit.
