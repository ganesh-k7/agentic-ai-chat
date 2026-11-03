"""All settings come from environment variables or `.env` (see .env.example)."""
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- chat model -------------------------------------------------------
    llm_provider: Literal["ollama", "gemini", "openai_compat"] = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    # Qwen3 / DeepSeek-R1 "think" before answering. "off" hides that for snappier chat.
    # Use "default" for models without a thinking mode if Ollama complains.
    ollama_think: Literal["off", "on", "default"] = "off"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    openai_base_url: str = ""          # e.g. https://api.groq.com/openai/v1
    openai_api_key: str = ""
    openai_model: str = ""

    # --- embeddings for RAG ----------------------------------------------
    embedding_provider: Literal["ollama", "gemini"] = "ollama"
    ollama_embed_model: str = "nomic-embed-text"
    gemini_embed_model: str = "models/gemini-embedding-001"

    # --- agent behaviour --------------------------------------------------
    workspace_dir: Path = Path("workspace")    # the only folder file/code tools can touch
    data_dir: Path = Path("data")              # sqlite checkpoints + chroma index
    require_approval: bool = True              # human must approve run_python
    max_history_messages: int = 40             # context window trimming
    recursion_limit: int = 30                  # max graph steps per request

    def ensure_dirs(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
