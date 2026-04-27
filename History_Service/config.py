from pydantic_settings import BaseSettings, SettingsConfigDict


class HistorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HIST_")

    port: int = 8002
    host: str = "0.0.0.0"

    # baza de date dedicata acestui serviciu (postgres-history in Docker)
    database_url: str = "postgresql://history_user:history_password@localhost:5433/history_db"

    sd_url: str = "http://localhost:8500"
    service_name: str = "history-service"
    service_url: str = "http://localhost:8002"

    jwt_public_key_path: str = "keys/public.pem"

    # numar maxim de mesaje trimise la model (sliding window, aplicat in frontend)
    history_window_size: int = 20


settings = HistorySettings()
