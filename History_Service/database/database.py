from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# conexiunea la PostgreSQL dedicata istoricului
engine = create_engine(settings.database_url)

# Fabrica de sesiuni
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clasa parinte pentru toate modelele SQLAlchemy din acest serviciu
Base = declarative_base()


def get_db():
    """
    Generator folosit ca dependency injection in FastAPI.
    Injectat cu Depends(get_db) in endpoint-uri.
    Garanteaza inchiderea sesiunii dupa fiecare request, chiar si la erori.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
