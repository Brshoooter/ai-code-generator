from pydantic_settings import BaseSettings, SettingsConfigDict

class ServiceDiscoverySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SD_")

    port: int = 8500
    host: str = "0.0.0.0"
    health_check_interval: int = 30
    service_response_timeout: int = 5
    fail_attempts: int = 3

settings = ServiceDiscoverySettings()