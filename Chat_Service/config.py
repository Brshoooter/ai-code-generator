from pydantic_settings import BaseSettings, SettingsConfigDict

class GenerateSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEN_")

    port: int = 8000
    host: str = "0.0.0.0"

    ollama_model: str = "codellama"
    ollama_temperature: float = 0.1
    ollama_repeat_penalty: float = 1.1
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = "15m"
    ollama_base_url: str = "http://localhost:11434"

    sd_url: str = "http://localhost:8500"
    service_name: str = "generate-service"
    service_url: str = "http://localhost:8000"


settings = GenerateSettings()