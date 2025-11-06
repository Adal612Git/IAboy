from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.emulator.config import ActionDefinition, DEFAULT_ACTION_MAP, EmulatorConfig
from app.emulator.manager import EmulatorManager
from app.emulator.models import FrameEnvelope, GameState, GameStepResult
from app.emulator.monitor import HealthMonitor
from app.emulator.session import EmulatorSession


class FakeEngine:
    """Minimal PyBoyEngine replacement for unit tests."""

    def __init__(self, config: EmulatorConfig) -> None:
        self.config = config
        self._rom_path: Path | None = None
        self._step_count = 0
        self._last_state: GameState | None = None
        self._saved_states: dict[Path, GameState] = {}

    @property
    def action_labels(self) -> tuple[str, ...]:
        return tuple(action.label for action in self.config.action_map)

    def start(self, rom_path: Path) -> GameState:
        self._rom_path = rom_path
        self._step_count = 0
        state = self._make_state(value=0)
        self._last_state = state
        return state

    def reset(self) -> GameState:
        if self._rom_path is None:
            raise RuntimeError("No ROM configured")
        return self.start(self._rom_path)

    def shutdown(self) -> None:
        self._last_state = None

    def capture_state(self) -> GameState:
        if not self._last_state:
            raise RuntimeError("Session not started")
        return self._last_state

    def step(self, action_label: str) -> GameStepResult:
        self._step_count += 1
        broken = action_label == "BROKEN"
        state = self._make_state(value=self._step_count, broken=broken)
        self._last_state = state
        info: dict[str, object] = {"action": action_label}
        return GameStepResult(
            new_state=state,
            reward=1.0 if not broken else 0.0,
            terminated=False,
            truncated=False,
            info=info,
        )

    def save_state(self, path: Path) -> Path:
        if not self._last_state:
            raise RuntimeError("No state available")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._saved_states[path] = self._last_state
        path.write_text(str(self._last_state.step_count))
        return path

    def load_state(self, path: Path) -> GameState:
        if path not in self._saved_states:
            raise FileNotFoundError(path)
        state = self._saved_states[path]
        self._last_state = state
        self._step_count = state.step_count
        return state

    def _make_state(self, *, value: int, broken: bool = False) -> GameState:
        if broken:
            pixels = np.empty((0,), dtype=np.uint8)
        else:
            pixels = np.full((144, 160, 3), value, dtype=np.uint8)
        frame = FrameEnvelope(pixels=pixels)
        return GameState(
            frame=frame,
            score=value,
            lives=3,
            progress=min(1.0, value / 10.0),
            step_count=value,
            memory_snapshot={"score": value},
        )


@pytest.fixture()
def rom_file(tmp_path: Path) -> Path:
    rom_path = tmp_path / "game.gb"
    rom_path.write_bytes(b"fake-rom")
    return rom_path


@pytest.fixture()
def emulator_config(tmp_path: Path, rom_file: Path) -> EmulatorConfig:
    actions = list(DEFAULT_ACTION_MAP)
    actions.append(ActionDefinition("BROKEN", tuple(), tuple()))
    return EmulatorConfig(
        roms_path=tmp_path,
        save_states_path=tmp_path / "saves",
        frame_dimensions=(144, 160, 3),
        frame_skip=1,
        autosave_interval_steps=2,
        health_check_interval_steps=1,
        max_consecutive_health_failures=1,
        action_map=tuple(actions),
        memory_watch_addresses={"score": 0},
        default_rom=str(rom_file),
        rom_extensions=(".gb", ".gbc"),
    )


def test_frame_envelope_serialisation() -> None:
    frame = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    envelope = FrameEnvelope(frame)
    envelope.validate((2, 2, 3))
    encoded = envelope.as_base64()
    assert isinstance(encoded, str)
    assert len(encoded) > 0


def test_health_monitor_detects_invalid_frame(emulator_config: EmulatorConfig) -> None:
    monitor = HealthMonitor(emulator_config)
    state = GameState(frame=FrameEnvelope(np.empty((0,), dtype=np.uint8)), step_count=1)
    status = monitor.evaluate(state, elapsed_time=0.01)
    assert not status.healthy
    assert status.consecutive_failures == 1
    assert status.needs_recovery is True


def test_session_recovers_after_failed_step(emulator_config: EmulatorConfig) -> None:
    engine = FakeEngine(emulator_config)
    monitor = HealthMonitor(emulator_config)
    session = EmulatorSession(emulator_config, engine, monitor)
    session.start(emulator_config.default_rom)
    first_result = session.step("NOOP")
    assert first_result.reward == pytest.approx(1.0)

    recovery_result = session.step("BROKEN")
    assert recovery_result.truncated is True
    assert recovery_result.info["recovered"] is True
    assert monitor.consecutive_failures == 0


def test_manager_creates_isolated_sessions(emulator_config: EmulatorConfig) -> None:
    engine_factory_calls: list[EmulatorConfig] = []

    def engine_factory(config: EmulatorConfig) -> FakeEngine:
        engine_factory_calls.append(config)
        return FakeEngine(config)

    manager = EmulatorManager(
        emulator_config,
        engine_factory=engine_factory,
        monitor_factory=lambda cfg: HealthMonitor(cfg),
    )
    session = manager.start_session(emulator_config.default_rom)
    assert session.session_id in [s.session_id for s in manager.list_sessions()]
    assert engine_factory_calls
    manager.shutdown()


def test_config_resolves_relative_path(emulator_config: EmulatorConfig, rom_file: Path) -> None:
    relative_path = rom_file.name
    resolved = emulator_config.resolve_rom_path(relative_path)
    assert resolved == rom_file
