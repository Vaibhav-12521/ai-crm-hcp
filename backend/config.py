from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = "your_groq_api_key_here"
    groq_model: str = "gemma2-9b-it"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/ai_crm"


settings = Settings()
