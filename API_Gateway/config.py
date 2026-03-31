from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GW_")

    port: int = 8080
    host: str = "0.0.0.0"

    sd_url: str = "http://localhost:8500"

    request_timeout: int = 60

    rate_limit_requests: int = 20
    rate_limit_time_window: int = 60

    cache_ttl: int = 30


settings = GatewaySettings()