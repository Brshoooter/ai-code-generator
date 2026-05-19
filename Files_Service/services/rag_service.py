"""
Orchestratorul pipeline-ului RAG (Retrieval Augmented Generation).

Acest modul leaga cele trei piese pe care le-am scris in Etapa 2/3:
  text_extractor  (bytes  → string)
  chunker         (string → list[str])
  embedder        (str    → list[float] de 768 dimensiuni)
  → bulk insert in tabela file_chunks

Si in plus, ofera functia de retrieval (pasul 4): primeste un query text,
il transforma in vector si cauta cele mai apropiate chunks din DB.

De ce un fisier separat (si nu logica direct in controller):
  - Controllerul (routes/files_controller.py) ramane subtire: HTTP in,
    HTTP out, cheama service-uri. Conventia MVC din CLAUDE.md.
  - Functiile de aici sunt reutilizabile (ex. ingest si retrieve folosesc
    ambele Embedder-ul; nu mai duplicam logica).
  - Daca maine vrem sa schimbam algoritmul de chunking sau modelul de
    embeddings, atingem doar acest fisier.

NU facem db.commit() aici — caller-ul (controller) detine tranzactia.
Asta ne lasa sa salvam atomar si FileRecord-ul si chunk-urile: daca ceva
pica pe drum, rollback-ul anuleaza ambele. Altfel am risca sa avem
chunks "orfani" in DB pentru un fisier care nu s-a salvat pana la capat.
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings
from models.file_model import FileChunk
from models.schemas import ChunkOut
from services import chunker, text_extractor
from services.embedder import Embedder

logger = logging.getLogger(__name__)

# Un singur Embedder per proces — nu tine state intern (doar config),
# deci e safe sa fie modul-level. AsyncClient-ul e creat per apel,
# vezi nota din embedder.py.
_embedder = Embedder()


async def embed_and_store_chunks(
    db: Session,
    file_id: UUID,
    content: bytes,
    mime_type: str,
    original_name: str,
) -> int:
    """
    Extrage text, il imparte in chunks, calculeaza embeddings, le adauga
    in sesiunea DB (FARA commit). Returneaza numarul de chunks adaugate.

    Parametri:
      db            — sesiunea SQLAlchemy detinuta de caller (controller)
      file_id       — UUID-ul deja generat pentru FileRecord (cheia
                      straina din file_chunks)
      content       — bytes-ii bruti ai fisierului (cititi din UploadFile)
      mime_type     — Content-Type validat anterior de quota_service
      original_name — numele original (folosit doar in log-uri)

    Returneaza int = nr chunks adaugate (poate fi 0 pentru PDF scanat
    fara text). Caller-ul foloseste valoarea ca sa populeze campul
    "chunks" din FileResponse.

    Ridica:
      RuntimeError  — daca Ollama pica sau modelul lipseste (propagat
                      din embedder). Controller-ul va trata exceptia
                      facand rollback la sesiune si delete la obiectul S3.
    """
    # 1. bytes → string (PDF prin pypdf, text/* prin UTF-8 decode).
    extracted_text = text_extractor.extract_text(content, mime_type, original_name)

    # 2. PDF scanat fara OCR / fisier text gol → renuntam la embeddings
    #    dar nu pica uploadul. Fisierul ramane salvat in S3 si listabil,
    #    doar ca nu va aparea in rezultatele /retrieve. Asta e o decizie
    #    constienta din plan (sectiunea 14 — riscuri cunoscute).
    if not extracted_text.strip():
        logger.warning(
            f"Fisier {original_name} ({mime_type}) a produs text gol — "
            "salvez fara embeddings."
        )
        return 0

    # 3. string mare → lista de stringuri scurte cu overlap pentru context.
    #    Vezi chunker.py pentru explicatia "de ce recursiv + de ce overlap".
    pieces = chunker.split(extracted_text)
    if not pieces:
        # Edge case: text non-gol dar splitter-ul returneaza []. Rar dar
        # posibil pe text format ciudat. Tratam la fel ca text gol.
        logger.warning(f"Chunker a returnat [] pentru {original_name}.")
        return 0

    logger.info(
        f"Embedding pentru {original_name}: {len(pieces)} chunks de "
        f"~{settings.chunk_size} chars."
    )

    # 4. Embeddings prin Ollama. Serial — vezi embedder.py pentru de ce.
    #    Daca un singur chunk pica, exceptia propaga si caller-ul face
    #    rollback la TOATA tranzactia (inclusiv FileRecord-ul daca era
    #    pus deja in sesiune).
    vectors = await _embedder.embed_many(pieces)

    # 5. Bulk insert: pregatim toate obiectele si le dam intr-un singur
    #    add_all. SQLAlchemy va emite un singur INSERT multi-row la commit,
    #    in loc de N round-trips la DB (mare diferenta pe PDF-uri lungi).
    chunk_records = [
        FileChunk(
            file_id=file_id,
            chunk_index=idx,
            content=piece,
            embedding=vec,
        )
        for idx, (piece, vec) in enumerate(zip(pieces, vectors))
    ]
    db.add_all(chunk_records)

    # NU facem commit aici — controllerul comit-eaza FileRecord + chunks
    # impreuna ca o singura tranzactie atomica.
    return len(chunk_records)


async def retrieve_chunks(
    db: Session,
    user_id: str,
    conversation_id: UUID,
    query: str,
    top_k: int,
) -> list[ChunkOut]:
    """
    Cauta cele mai relevante chunks pentru un query, restrictionat la
    fisierele userului din conversatia data.

    Pasi:
      1. embed query-ul cu acelasi model ca la ingest (altfel vectorii
         nu sunt comparabili — modele diferite produc spatii diferite).
      2. SQL cu operatorul "<=>" din pgvector (distanta cosine).
         ORDER BY ASC inseamna "cel mai apropiat primul".
      3. Filtru obligatoriu pe user_id + conversation_id — un user nu
         poate vedea chunks din fisierele altcuiva nici daca ghiceste
         conv_id-ul (varianta "trust-on-JWT + WHERE" din plan).

    Scoring: cosine distance e in [0, 2] (0 = identic, 2 = opus).
    "score" returnat = 1 - distance, deci in [-1, 1]; mai mare = mai
    similar. Util pentru afisare/debug, NU folosit ca filtru hard
    (intoarcem mereu top_k indiferent de score).
    """
    # 1. query → vector. Refoloseste acelasi Embedder ca la ingest.
    query_vec = await _embedder.embed_one(query)

    # 2. SQL raw cu pgvector. SQLAlchemy ORM nu stie nativ operatorul
    #    "<=>", deci scriem text() explicit. Bind-am parametrii (NU
    #    interpolam stringuri) ca sa nu fim vulnerabili la SQL injection.
    #
    #    Vectorul se trimite ca string in format "[0.1, 0.2, ...]";
    #    pgvector il parseaza automat pe partea de Postgres. Asta e
    #    conventia cea mai portabila — alternativa cu psycopg2 adapter
    #    ar fi mai eleganta dar adauga setup.
    vec_literal = "[" + ",".join(str(x) for x in query_vec) + "]"

    sql = text("""
        SELECT
            fc.content        AS content,
            fc.chunk_index    AS chunk_index,
            f.original_name   AS file_name,
            (fc.embedding <=> CAST(:qvec AS vector)) AS distance
        FROM file_chunks fc
        JOIN files f ON f.id = fc.file_id
        WHERE f.user_id = :uid
          AND f.conversation_id = :cid
        ORDER BY fc.embedding <=> CAST(:qvec AS vector)
        LIMIT :k
    """)

    rows = db.execute(
        sql,
        {
            "qvec": vec_literal,
            "uid": user_id,
            "cid": str(conversation_id),
            "k": top_k,
        },
    ).fetchall()

    # 3. Row → ChunkOut. SQLAlchemy 2.x returneaza Row obiecte cu
    #    acces atat prin index cat si prin nume — folosim ._mapping
    #    ca sa iteram clar dupa cheile coloanelor.
    results: list[ChunkOut] = []
    for row in rows:
        m = row._mapping
        results.append(
            ChunkOut(
                content=m["content"],
                file_name=m["file_name"],
                chunk_index=m["chunk_index"],
                score=1.0 - float(m["distance"]),
            )
        )
    return results
