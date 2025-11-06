"""Application configuration settings for the IAboy backend."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Settings loaded from environment variables with sensible defaults."""

    api_prefix: str = Field(
        "/api",
        description="Prefix used for all API routes exposed by the FastAPI application.",
    )
    ollama_url: str = Field(
        "http://localhost:11434",
        description="Base URL of the local Ollama service hosting Gemma 2.",
    )
    ollama_model: str = Field(
        "gemma2:2b",
        description="Name of the Gemma 2 model served by Ollama.",
    )
    roms_path: Path = Field(
        Path("roms"),
        description="Directory where game ROM files are stored.",
    )
    save_states_path: Path = Field(
        Path("save_states"),
        description="Directory where game save states are stored.",
    )
    frame_skip: int = Field(
        4,
        description=(
            "Number of emulator frames to skip between observations to reduce the "
            "amount of data sent to the LLM."
        ),
    )
    available_games: List[str] = Field(
        default_factory=lambda: [
            "SuperMarioBros-Nes",
            "SonicTheHedgehog-Genesis",
            "PokemonRed-GameBoy",
        ],
        description="List of ROM identifiers supported by default.",
    )

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("roms_path", "save_states_path", pre=True)
    def _expand_path(cls, value: Path | str) -> Path:  # noqa: D401
        """Ensure configured paths are absolute and exist."""

        path = Path(value).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""

    return Settings()
