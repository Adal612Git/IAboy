"""Application configuration settings for the IAboy backend."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        "gemma2:9b",
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
        1,
        ge=1,
        description=(
            "Number of emulator ticks executed for each requested step. A value of 1 "
            "keeps the emulation perfectly synchronised with client commands."
        ),
    )
    autosave_interval_steps: int = Field(
        120,
        ge=1,
        description="How many steps to wait before persisting an automatic save state.",
    )
    health_check_interval_steps: int = Field(
        1,
        ge=1,
        description=(
            "Frequency (in steps) at which the health monitor validates captured frames."
        ),
    )
    max_consecutive_health_failures: int = Field(
        3,
        ge=1,
        description="Number of failed health checks tolerated before recovery is triggered.",
    )
    frame_dimensions: Tuple[int, int, int] = Field(
        (144, 160, 3),
        description="Expected frame dimensions produced by the Game Boy emulator.",
    )
    default_rom: Optional[str] = Field(
        None,
        description=(
            "Optional default ROM filename used when clients start the emulator without "
            "specifying a target."
        ),
    )
    memory_watch_addresses: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Dictionary of symbolic names mapped to memory addresses that should be "
            "sampled on each step to compute rewards and high level game metrics."
        ),
    )
    rom_extensions: Tuple[str, ...] = Field(
        (".gb", ".gbc"),
        description="Accepted ROM file extensions for the PyBoy emulator backend.",
    )
    available_games: List[str] = Field(
        default_factory=list,
        description=(
            "Backwards-compatible list of detected ROM identifiers. The PyBoy backend "
            "does not enforce this whitelist and accepts any valid Game Boy ROM file."
        ),
    )

    class Config:
        env_file = "../.env"
        case_sensitive = False

    @validator("roms_path", "save_states_path", pre=True)
    def _expand_path(cls, value: Path | str) -> Path:  # noqa: D401
        """Ensure configured paths are absolute and exist."""

        path = Path(value).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @validator("available_games", always=True)
    def _load_available_games(cls, v: list[str], values: dict) -> list[str]:
        """Scan the configured ROMs path to discover available games."""

        roms_path = values.get("roms_path")
        if roms_path and roms_path.is_dir():
            return sorted([p.stem for p in roms_path.glob("*") if p.is_file()])
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""

    return Settings()
