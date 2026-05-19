"""
Splitter de text pentru pipeline-ul RAG.

Scop: dat un text mare (poate mii de caractere — un PDF de 5 MB sau un
fisier .py mare), il taiem in bucati mai mici ("chunks") care:
  - intra in fereastra modelului de embeddings (nomic-embed-text accepta
    pana la ~8192 tokens, dar e mai eficient pe bucati de ~500-1000 chars);
  - sunt suficient de mici ca search-ul vectorial sa fie precis (un chunk
    de 100 KB ar avea un singur vector "mediu" care nu reprezinta bine
    nicio sub-tema);
  - sunt suficient de mari ca sa pastreze context (un chunk de 50 chars
    ar fi prea fragmentat pentru ca modelul sa inteleaga sensul).

De ce splitter "recursiv":
  - Naive: imparte la fiecare N caractere → poti taia un cuvant in doua,
    sau o functie Python intr-un loc fara sens.
  - Recursive: incearca sa taie mai intai la separatori "mari" (paragrafe
    "\\n\\n"), apoi la "\\n", apoi la ". ", apoi la spatii, si abia in
    ultima instanta la nivel de caracter. Asa pastreaza unitati semantice
    cat se poate de mult.

De ce "overlap" intre chunks:
  - Daca un chunk se termina la jumatatea unei propozitii si urmatorul
    incepe imediat, query-urile RAG care cer continuitate ar pierde context.
  - Cu overlap = 100 chars, ultimele 100 chars din chunk N apar si la
    inceputul chunk-ului N+1 — asigura ca o idee taiata fix pe granita
    apare in cel putin un chunk complet.

Apelat de: rag_service.ingest_file (Etapa 3), imediat dupa text_extractor.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings


def split(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """
    Imparte un text in chunks folosind RecursiveCharacterTextSplitter.

    Parametri (toti optionali — default-urile vin din settings):
      text       — textul integral extras din fisier
      chunk_size — marimea tinta in caractere (default settings.chunk_size = 800)
      overlap    — cate caractere se suprapun intre chunks consecutive
                   (default settings.chunk_overlap = 100)

    Returneaza o lista de stringuri. Lista poate fi goala daca text-ul
    e gol (PDF scanat fara OCR) — caller-ul trebuie sa trateze cazul.

    Separatorii sunt incercati in ordinea data: intai "\\n\\n" (paragrafe),
    apoi "\\n" (linii), apoi ". " (propozitii), apoi " " (cuvinte), si in
    final "" (caracter — fallback ca splitter-ul sa termine garantat).
    """
    cs = chunk_size if chunk_size is not None else settings.chunk_size
    ov = overlap if overlap is not None else settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cs,
        chunk_overlap=ov,
        separators=["\n\n", "\n", ". ", " ", ""],
        # length_function default e len() pe caractere — perfect pentru
        # estimarea grosiera. Pentru token-precision am putea folosi
        # tiktoken sau modelul Ollama, dar nu merita complexitatea aici.
    )

    # split_text accepta string si returneaza list[str]. Daca textul
    # e mai scurt decat chunk_size, returneaza o lista cu un singur element.
    # Daca textul e gol, returneaza [].
    return splitter.split_text(text)
