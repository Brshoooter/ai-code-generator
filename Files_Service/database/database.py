from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# conexiunea la PostgreSQL dedicata fisierelor (postgres-files in Docker)
engine = create_engine(settings.database_url)

# fabrica de sesiuni — autocommit=False inseamna ca trebuie sa apelam explicit commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# clasa parinte pentru modelele SQLAlchemy din acest serviciu
Base = declarative_base()


def get_db():
    """
    Dependency injection pentru FastAPI — injectat cu Depends(get_db) in route-uri.
    Garanteaza inchiderea sesiunii dupa fiecare request, chiar si la exceptii.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_pgvector_extension():
    """
    Creeaza extensia "vector" daca nu exista. Trebuie rulat INAINTE de
    Base.metadata.create_all, pentru ca tabela file_chunks foloseste
    coloana de tip Vector(768) — fara extensie, CREATE TABLE da eroare.
    Imaginea pgvector/pgvector:pg16 are deja binarele instalate; comanda
    asta doar le activeaza in baza noastra de date.

    Folosim un context "begin()" ca SQLAlchemy sa faca commit automat
    la final (CREATE EXTENSION e DDL si trebuie commitat).
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
