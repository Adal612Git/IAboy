"""Core PyBoy engine wrapper providing a deterministic, testable API."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np

from .config import ActionDefinition, EmulatorConfig
from .models import FrameEnvelope, GameState, GameStepResult


class PyBoyEngine:
    """High level façade around :class:`pyboy.PyBoy` used by the backend."""

    def __init__(
        self,
        config: EmulatorConfig,
        pyboy_factory: Optional[Callable[[Path], object]] = None,
    ) -> None:
        self.config = config
        self._pyboy_factory = pyboy_factory or self._default_factory
        self._pyboy: Optional[object] = None
        self._window = None
        self._rom_path: Optional[Path] = None
        self._step_count = 0
        self._last_score = 0
        self._last_state: Optional[GameState] = None

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    def start(self, rom_path: Path) -> GameState:
        """Initialise PyBoy with the provided ROM and return the initial state."""

        self.shutdown()
        self._rom_path = rom_path
        self._pyboy = self._pyboy_factory(rom_path)
        self._configure_runtime()
        self._step_count = 0
        self._last_score = 0
        self._last_state = self._capture_state()
        return self._last_state

    def reset(self) -> GameState:
        """Reset the current ROM by reloading it from disk."""

        if self._rom_path is None:
            raise RuntimeError("No ROM has been initialised yet.")
        return self.start(self._rom_path)

    def shutdown(self) -> None:
        """Gracefully close the PyBoy instance if one is running."""

        if self._pyboy is not None:
            close = getattr(self._pyboy, "close", None)
            if callable(close):
                close()
        self._pyboy = None
        self._window = None
        self._last_state = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def rom_path(self) -> Optional[Path]:
        return self._rom_path

    @property
    def action_labels(self) -> tuple[str, ...]:
        return tuple(action.label for action in self.config.action_map)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def step(self, action_label: str) -> GameStepResult:
        """Execute one step in the emulator using the requested action."""

        if self._pyboy is None:
            raise RuntimeError("PyBoy has not been initialised. Call start() first.")

        action = self._resolve_action(action_label)
        self._dispatch_events(action.press_events)

        for _ in range(self.config.frame_skip):
            self._tick()

        if action.release_events:
            self._dispatch_events(action.release_events)

        self._step_count += 1
        state = self._capture_state()
        reward = self._calculate_reward(state)
        info = {
            "step_count": self._step_count,
            "rom": str(self._rom_path) if self._rom_path else None,
            "frame_shape": list(state.frame.pixels.shape),
            "frame_timestamp": state.frame.timestamp,
        }
        result = GameStepResult(
            new_state=state,
            reward=reward,
            terminated=state.is_game_over,
            truncated=False,
            info=info,
        )
        self._last_state = state
        return result

    def capture_state(self) -> GameState:
        """Return the most recently captured state without advancing the emulator."""

        if self._last_state is None:
            raise RuntimeError("No state available; ensure start() has been called.")
        return self._last_state

    def save_state(self, path: Path) -> Path:
        """Serialise the current emulator state to *path*."""

        if self._pyboy is None:
            raise RuntimeError("PyBoy has not been initialised. Call start() first.")
        ensure_path(path)
        with path.open("wb") as handle:
            self._pyboy.save_state(handle)  # type: ignore[attr-defined]
        return path

    def load_state(self, path: Path) -> GameState:
        """Load the emulator state from *path* and return the resulting snapshot."""

        if self._pyboy is None:
            raise RuntimeError("PyBoy has not been initialised. Call start() first.")
        with path.open("rb") as handle:
            self._pyboy.load_state(handle)  # type: ignore[attr-defined]
        # Run one tick to allow the emulator to settle on the restored state.
        self._tick()
        self._last_state = self._capture_state()
        return self._last_state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _default_factory(self, rom_path: Path) -> object:
        try:
            from pyboy import PyBoy
        except ImportError as exc:  # pragma: no cover - exercised in integration
            raise RuntimeError(
                "PyBoy no está instalado. Instálalo con `pip install pyboy`."
            ) from exc

        pyboy = PyBoy(str(rom_path), window_type="headless", game_speed=0)
        # Explicitly request deterministic execution speed.
        if hasattr(pyboy, "set_emulation_speed"):
            pyboy.set_emulation_speed(0)  # type: ignore[attr-defined]
        return pyboy

    def _configure_runtime(self) -> None:
        if self._pyboy is None:
            return
        self._window = getattr(self._pyboy, "window", None)
        if self._window is None and hasattr(self._pyboy, "get_window"):
            self._window = self._pyboy.get_window()

    def _tick(self) -> None:
        if self._pyboy is None:
            raise RuntimeError("PyBoy has not been initialised. Call start() first.")
        tick = getattr(self._pyboy, "tick", None)
        if not callable(tick):
            raise RuntimeError("The PyBoy instance does not expose a tick() method.")
        tick()

    def _resolve_action(self, label: str) -> ActionDefinition:
        for action in self.config.action_map:
            if action.label == label:
                return action
        raise ValueError(f"Acción desconocida: {label}")

    def _dispatch_events(self, events: Iterable[str]) -> None:
        if not events:
            return
        if self._window is None:
            raise RuntimeError("La ventana de PyBoy no está inicializada.")
        for event_name in events:
            event = self._resolve_window_event(event_name)
            self._window.send_input(event)  # type: ignore[attr-defined]

    def _resolve_window_event(self, event_name: str):
        try:
            from pyboy.utils import WindowEvent
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pyboy.utils.WindowEvent no está disponible. Verifica la instalación de PyBoy."
            ) from exc
        if not hasattr(WindowEvent, event_name):
            raise ValueError(f"Evento de ventana desconocido: {event_name}")
        return getattr(WindowEvent, event_name)

    def _capture_state(self) -> GameState:
        frame = self._capture_frame()
        memory_snapshot = self._capture_memory()
        frame.validate(self.config.frame_dimensions)
        state = GameState(
            frame=frame,
            is_game_over=bool(memory_snapshot.get("game_over", False)),
            paused=bool(getattr(self._pyboy, "paused", False)),
            score=memory_snapshot.get("score"),
            lives=memory_snapshot.get("lives"),
            progress=memory_snapshot.get("progress"),
            step_count=self._step_count,
            memory_snapshot=memory_snapshot,
        )
        return state

    def _capture_frame(self) -> FrameEnvelope:
        if self._pyboy is None:
            raise RuntimeError("PyBoy has not been initialised. Call start() first.")
        frame_array = None
        # Try bot-support first which returns numpy arrays directly.
        if hasattr(self._pyboy, "botsupport_manager"):
            manager = self._pyboy.botsupport_manager()
            if manager and hasattr(manager, "screen"):
                screen = manager.screen()
                if screen is not None and hasattr(screen, "screen_ndarray"):
                    frame_array = screen.screen_ndarray()
        if frame_array is None and hasattr(self._pyboy, "screen_image"):
            image = self._pyboy.screen_image()
            frame_array = np.array(image, copy=False)
        if frame_array is None:
            raise RuntimeError("PyBoy no pudo proporcionar un frame de video.")
        return FrameEnvelope(pixels=frame_array)

    def _capture_memory(self) -> dict[str, int]:
        snapshot: dict[str, int] = {}
        if self._pyboy is None:
            return snapshot
        if not self.config.memory_watch_addresses:
            return snapshot
        for name, address in self.config.memory_watch_addresses.items():
            try:
                value = int(self._pyboy.get_memory_value(address))  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive path
                value = -1
            snapshot[name] = value
        return snapshot

    def _calculate_reward(self, state: GameState) -> float:
        score = state.score if state.score is not None else 0
        reward = float(score - self._last_score)
        self._last_score = score
        return reward


def ensure_path(path: Path) -> Path:
    """Utility ensuring that the parent directories of *path* exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    return path
