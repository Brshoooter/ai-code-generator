from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_")

    port: int = 8001
    host: str = "0.0.0.0"

    database_url: str = "postgresql://auth_user:auth_password@localhost:5432/auth_db"

    sd_url: str = "http://localhost:8500"
    service_name: str = "auth-service"
    service_url: str = "http://localhost:8001"

    jwt_expiry_minutes: int = 30
    jwt_private_key_path: str = "keys/private.pem"
    jwt_public_key_path: str = "keys/public.pem"


settings = AuthSettings()
