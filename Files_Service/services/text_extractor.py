"""
Extragere text brut dintr-un fisier urcat de utilizator.

Scop: convertim continutul binar al fisierului (PDF, .py, .md, .txt etc.)
intr-un singur string Unicode pe care il putem da mai departe la chunker
si apoi la modelul de embeddings.

De ce avem nevoie de modulul asta:
  - PDF-urile sunt format binar; nu poti face decode("utf-8") pe ele.
    Trebuie un parser care intelege structura PDF (pagini, fonts, encoding-uri
    interne) si scoate textul vizibil. Folosim pachetul "pypdf".
  - Fisierele text (cod sursa, markdown) sunt in principiu UTF-8, dar pot
    veni din Windows cu encoding diferit (latin-1, cp1252). Nu vrem sa
    crape uploadul daca un user are un fisier cu un caracter non-UTF-8.

Apelat de: rag_service.ingest_file (in Etapa 3) imediat dupa ce s3_client
a salvat continutul. Primeste bytes-ii bruti + mime type-ul declarat si
returneaza un string. NU ridica exceptie pe text gol — lasa caller-ul sa
decida (un PDF scanat fara OCR e text gol, dar fisierul ramane salvat in
S3 fara chunks).
"""

import io
import logging

logger = logging.getLogger(__name__)


def extract_text(content: bytes, mime_type: str, original_name: str) -> str:
    """
    Routeaza extragerea pe baza MIME type-ului.

    Parametri:
      content       — continutul binar al fisierului (bytes)
      mime_type     — Content-Type declarat (deja validat de quota_service)
      original_name — numele fisierului, doar pentru log-uri (debugging)

    Returneaza un string. Poate fi gol pentru PDF-uri scanate (imagini)
    sau fisiere text complet binare; caller-ul trebuie sa trateze cazul.
    """
    if mime_type == "application/pdf":
        return _extract_pdf(content, original_name)

    # Toate celelalte tipuri permise sunt text plain (cod sursa, markdown).
    # errors="replace" inlocuieste bytes invalizi cu U+FFFD in loc sa crape;
    # preferam un text cu cateva caractere ciudate fata de un upload esuat.
    try:
        return content.decode("utf-8", errors="replace")
    except Exception as e:
        # Defensiv — decode("utf-8", errors="replace") nu ar trebui sa
        # crape niciodata, dar daca se intampla (ex. memoryview corupt),
        # incercam latin-1 care accepta orice byte ca un caracter.
        logger.warning(
            f"Decode UTF-8 esuat pentru {original_name}: {e}. Incerc latin-1."
        )
        return content.decode("latin-1", errors="replace")


def _extract_pdf(content: bytes, original_name: str) -> str:
    """
    Foloseste pypdf pentru a parcurge paginile si a concatena textul.

    pypdf.PdfReader citeste structura PDF dintr-un file-like object;
    BytesIO impacheteaza bytes-ii nostri ca un fisier in memorie, fara
    sa scriem nimic pe disk.

    page.extract_text() returneaza None pentru pagini fara text (imagini
    scanate). Filtram cu "or '' " ca join-ul sa nu pice cu TypeError.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages_text)
    except Exception as e:
        # PDF corupt sau cu encryption — log si returneaza gol.
        # Caller-ul va vedea len(text) == 0 si va sari peste embedding.
        logger.warning(f"Extragere PDF esuata pentru {original_name}: {e}")
        return ""

    if len(text.strip()) < 10:
        # Heuristica: PDF scanat fara OCR. Loggam ca utilizatorul sa stie
        # de ce fisierul lui nu apare in rezultatele RAG.
        logger.warning(
            f"PDF {original_name} a produs text foarte scurt ({len(text)} chars). "
            "Posibil PDF scanat fara OCR — fisierul ramane salvat dar fara embeddings."
        )

    return text
