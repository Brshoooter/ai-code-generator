from pydantic_settings import BaseSettings, SettingsConfigDict


class FilesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FILES_")

    port: int = 8003
    host: str = "0.0.0.0"

    # Service Discovery
    sd_url: str = "http://service-discovery:8500"
    service_url: str = "http://files-service:8003"
    service_name: str = "files-service"

    # baza de date dedicata (postgres-files in Docker)
    database_url: str = "postgresql+psycopg2://files_user:files_pass@postgres-files:5432/files_db"

    # JWT (defense in depth — la fel ca in History Service)
    jwt_public_key_path: str = "keys/public.pem"
    jwt_algorithm: str = "RS256"

    # Ollama pentru embeddings
    ollama_base_url: str = "http://host.docker.internal:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # parametrii de chunking pentru RAG
    chunk_size: int = 800
    chunk_overlap: int = 100

    # limite de upload
    max_file_bytes: int = 5 * 1024 * 1024            # 5 MB per fisier
    max_files_per_conversation: int = 5
    max_total_bytes_per_user: int = 50 * 1024 * 1024  # 50 MB total per user

    # numarul de chunks returnate la retrieval
    retrieve_top_k: int = 4

    # tipuri MIME permise (CSV, parsate in services/)
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

    # AWS S3 (gol = stub local pe disk, fara cont AWS)
    aws_region: str = "eu-central-1"
    s3_bucket: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_local_stub_dir: str = "/tmp/local-files-bucket"


settings = FilesSettings()
