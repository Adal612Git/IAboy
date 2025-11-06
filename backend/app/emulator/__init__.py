"""PyBoy-based emulation backend for the retro AI experiment."""

from .config import EmulatorConfig, build_emulator_config
from .manager import EmulatorManager

__all__ = [
    "EmulatorConfig",
    "EmulatorManager",
    "build_emulator_config",
]
