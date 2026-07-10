from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str
    groq_api_key: str
    google_sheets_webhook_url: str = ""
    manager_telegram_chat_id: str = ""
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_model: str = "llama-3.3-70b-versatile"
    openai_fallback_model: str = "llama-3.1-8b-instant"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 300
    max_history_messages: int = 10
    max_rag_chunks: int = 3

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def system_prompt_path(self) -> Path:
        return self.project_root / "prompts" / "system.md"

    @property
    def knowledge_dir(self) -> Path:
        return self.project_root / "knowledge"


settings = Settings()
