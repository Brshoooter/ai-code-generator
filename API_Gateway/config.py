from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GW_")

    port: int = 8080
    host: str = "0.0.0.0"

    sd_url: str = "http://localhost:8500"

    request_timeout: int = 60

    # Limita pentru cereri autentificate, contorizate pe user_id.
    rate_limit_user_requests: int = 60
    # Limita pentru cereri anonime (login, register), contorizate pe IP. Anti-brute-force.
    rate_limit_anon_requests: int = 10
    rate_limit_time_window: int = 60

    cache_ttl: int = 30

    jwt_public_key_path: str = "keys/public.pem"


settings = GatewaySettings()