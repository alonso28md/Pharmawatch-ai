"""Centralized application configuration, loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings sourced from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic / Claude
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5-5", alias="ANTHROPIC_MODEL")
    llm_timeout_seconds: float = Field(default=60.0, alias="LLM_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Storage
    db_path: str = Field(default="data/pharmawatch.db", alias="DB_PATH")
    chroma_persist_dir: str = Field(default="data/chroma_db", alias="CHROMA_PERSIST_DIR")

    # RAG chunking / retrieval
    chunk_size: int = Field(default=800, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")

    # API
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000", alias="CORS_ORIGINS"
    )
    api_key: str = Field(default="", alias="API_KEY")
    # Without API_KEY the cost-bearing endpoints are disabled unless this is set explicitly.
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    rate_limit_per_minute: int = Field(default=30, alias="RATE_LIMIT_PER_MINUTE")
    max_request_bytes: int = Field(default=64_000, alias="MAX_REQUEST_BYTES")

    # Evaluation: only these named datasets (name=file under data/) may be run via the API.
    evaluation_datasets: str = Field(
        default="default=golden_dataset.json,v2=golden_dataset_v2.json",
        alias="EVALUATION_DATASETS",
    )
    # Evaluation outputs are data, not docs: written here, never under docs/ or into the DB.
    artifacts_dir: str = Field(default="artifacts", alias="ARTIFACTS_DIR")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def evaluation_dataset_files(self) -> dict[str, Path]:
        """Whitelisted dataset name -> absolute path under data/."""
        datasets: dict[str, Path] = {}
        for entry in self.evaluation_datasets.split(","):
            name, sep, filename = entry.strip().partition("=")
            if sep and name and filename:
                datasets[name.strip()] = PROJECT_ROOT / "data" / Path(filename.strip()).name
        return datasets

    @property
    def artifacts_dir_absolute(self) -> Path:
        path = Path(self.artifacts_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def db_path_absolute(self) -> Path:
        path = Path(self.db_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def chroma_persist_dir_absolute(self) -> Path:
        path = Path(self.chroma_persist_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
