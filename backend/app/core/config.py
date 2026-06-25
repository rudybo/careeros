from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "CareerOS"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./careeros.db"

    # LLM provider: "groq" (cloud) o "ollama" (locale)
    llm_provider: str = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_api_key: str = ""


settings = Settings()
