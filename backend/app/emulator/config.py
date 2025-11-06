"""Configuration objects and defaults for the PyBoy emulation backend."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from ..core.config import Settings


@dataclass(frozen=True)
class ActionDefinition:
    """Represents a single emulator action and its associated input events."""

    label: str
    press_events: Tuple[str, ...] = field(default_factory=tuple)
    release_events: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:  # noqa: D401
        """Validate that no empty string events are configured."""

        if any(event == "" for event in (*self.press_events, *self.release_events)):
            raise ValueError("Action events cannot contain empty strings.")


DEFAULT_ACTION_MAP: Tuple[ActionDefinition, ...] = (
    ActionDefinition("NOOP", tuple(), tuple()),
    ActionDefinition(
        "UP",
        ("PRESS_ARROW_UP",),
        ("RELEASE_ARROW_UP",),
    ),
    ActionDefinition(
        "DOWN",
        ("PRESS_ARROW_DOWN",),
        ("RELEASE_ARROW_DOWN",),
    ),
    ActionDefinition(
        "LEFT",
        ("PRESS_ARROW_LEFT",),
        ("RELEASE_ARROW_LEFT",),
    ),
    ActionDefinition(
        "RIGHT",
        ("PRESS_ARROW_RIGHT",),
        ("RELEASE_ARROW_RIGHT",),
    ),
    ActionDefinition(
        "A",
        ("PRESS_BUTTON_A",),
        ("RELEASE_BUTTON_A",),
    ),
    ActionDefinition(
        "B",
        ("PRESS_BUTTON_B",),
        ("RELEASE_BUTTON_B",),
    ),
    ActionDefinition(
        "START",
        ("PRESS_BUTTON_START",),
        ("RELEASE_BUTTON_START",),
    ),
    ActionDefinition(
        "SELECT",
        ("PRESS_BUTTON_SELECT",),
        ("RELEASE_BUTTON_SELECT",),
    ),
)


@dataclass
class EmulatorConfig:
    """Aggregated configuration values used by the emulator subsystem."""

    roms_path: Path
    save_states_path: Path
    frame_dimensions: Tuple[int, int, int]
    frame_skip: int
    autosave_interval_steps: int
    health_check_interval_steps: int
    max_consecutive_health_failures: int
    action_map: Tuple[ActionDefinition, ...]
    memory_watch_addresses: Mapping[str, int]
    default_rom: Optional[str]
    rom_extensions: Tuple[str, ...]

    def resolve_rom_path(self, rom_reference: Optional[str]) -> Path:
        """Resolve the target ROM path ensuring the extension is supported."""

        candidate = rom_reference or self.default_rom
        if not candidate:
            raise ValueError(
                "No ROM provided and no default ROM configured. "
                "Pass an explicit ROM path in the /start request."
            )
        rom_path = Path(candidate)
        if not rom_path.is_absolute():
            rom_path = self.roms_path / rom_path
        rom_path = rom_path.expanduser().resolve()
        if rom_path.suffix.lower() not in {ext.lower() for ext in self.rom_extensions}:
            raise ValueError(
                f"La ROM '{rom_path}' no tiene una extensión soportada: {self.rom_extensions}."
            )
        if not rom_path.exists():
            raise FileNotFoundError(f"La ROM '{rom_path}' no existe.")
        return rom_path

    def to_dict(self) -> Dict[str, object]:
        """Return a serialisable representation useful for debugging and health APIs."""

        return {
            "roms_path": str(self.roms_path),
            "save_states_path": str(self.save_states_path),
            "frame_dimensions": self.frame_dimensions,
            "frame_skip": self.frame_skip,
            "autosave_interval_steps": self.autosave_interval_steps,
            "health_check_interval_steps": self.health_check_interval_steps,
            "max_consecutive_health_failures": self.max_consecutive_health_failures,
            "default_rom": self.default_rom,
            "rom_extensions": self.rom_extensions,
            "action_labels": [action.label for action in self.action_map],
            "memory_watch_addresses": dict(self.memory_watch_addresses),
        }


def build_emulator_config(settings: Settings) -> EmulatorConfig:
    """Create an :class:`EmulatorConfig` instance from application settings."""

    action_labels = {action.label for action in DEFAULT_ACTION_MAP}
    configured_actions: MutableMapping[str, ActionDefinition] = {
        action.label: action for action in DEFAULT_ACTION_MAP
    }

    # Allow overriding action bindings from environment variables. Each entry must
    # be encoded as LABEL=EVENT1|EVENT2;EVENT3|EVENT4 where the first group defines
    # press events and the second optional group defines release events.
    for label, encoded in getattr(settings, "action_overrides", {}).items():  # type: ignore[attr-defined]
        if label not in action_labels:
            raise ValueError(f"Acción desconocida al configurar PyBoy: {label}")
        segments = encoded.split(";")
        press_events = tuple(filter(None, segments[0].split("|"))) if segments else tuple()
        release_events: Iterable[str] = tuple()
        if len(segments) > 1:
            release_events = tuple(filter(None, segments[1].split("|")))
        configured_actions[label] = ActionDefinition(label, press_events, tuple(release_events))

    return EmulatorConfig(
        roms_path=settings.roms_path,
        save_states_path=settings.save_states_path,
        frame_dimensions=settings.frame_dimensions,
        frame_skip=settings.frame_skip,
        autosave_interval_steps=settings.autosave_interval_steps,
        health_check_interval_steps=settings.health_check_interval_steps,
        max_consecutive_health_failures=settings.max_consecutive_health_failures,
        action_map=tuple(configured_actions[label] for label in sorted(configured_actions)),
        memory_watch_addresses=settings.memory_watch_addresses,
        default_rom=settings.default_rom,
        rom_extensions=settings.rom_extensions,
    )
