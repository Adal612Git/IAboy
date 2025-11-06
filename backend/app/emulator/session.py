"""Session management coordinating engine, monitoring and persistence."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from .config import EmulatorConfig
from .engine import PyBoyEngine
from .models import GameState, GameStepResult, HealthStatus
from .monitor import HealthMonitor


class EmulatorSession:
    """Encapsulates a running PyBoy emulator instance."""

    def __init__(
        self,
        config: EmulatorConfig,
        engine: PyBoyEngine,
        monitor: HealthMonitor,
        *,
        session_id: Optional[str] = None,
    ) -> None:
        self.config = config
        self.engine = engine
        self.monitor = monitor
        self.session_id = session_id or uuid.uuid4().hex
        self._active = False
        self._last_result: Optional[GameStepResult] = None
        self._last_health: Optional[HealthStatus] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self, rom_reference: Optional[str]) -> GameState:
        rom_path = self.config.resolve_rom_path(rom_reference)
        initial_state = self.engine.start(rom_path)
        self.monitor.reset()
        baseline_path = self.save_state()
        self.monitor.remember_save_path(baseline_path)
        self._active = True
        self._last_health = self.monitor.evaluate(initial_state, elapsed_time=0.0)
        return initial_state

    def step(self, action_label: str) -> GameStepResult:
        if not self._active:
            raise RuntimeError("The emulator session has not been started yet.")
        start = time.perf_counter()
        result = self.engine.step(action_label)
        elapsed = time.perf_counter() - start

        if self.monitor.should_run_check(result.new_state.step_count):
            health_status = self.monitor.evaluate(result.new_state, elapsed_time=elapsed)
            self._last_health = health_status
        else:
            health_status = self._last_health

        if health_status and not health_status.healthy:
            recovered_state = self._perform_recovery()
            result = GameStepResult(
                new_state=recovered_state,
                reward=0.0,
                terminated=False,
                truncated=True,
                info={
                    "recovered": True,
                    "reason": list(health_status.issues),
                    "step_count": recovered_state.step_count,
                },
            )
        else:
            result.info.setdefault("health", self._health_payload())

        if result.new_state.step_count % self.config.autosave_interval_steps == 0:
            self.save_state()

        self._last_result = result
        return result

    def current_state(self) -> GameState:
        return self.engine.capture_state()

    @property
    def action_labels(self) -> tuple[str, ...]:
        return self.engine.action_labels

    def current_health(self) -> dict[str, object]:
        return self._health_payload()

    def reset(self) -> GameState:
        state = self.engine.reset()
        self.monitor.reset()
        baseline_path = self.save_state()
        self.monitor.remember_save_path(baseline_path)
        self._last_health = self.monitor.evaluate(state, elapsed_time=0.0)
        self._last_result = None
        return state

    def save_state(self) -> Path:
        filename = f"{self.session_id}-{int(time.time() * 1000)}.state"
        path = self.config.save_states_path / filename
        saved_path = self.engine.save_state(path)
        self.monitor.remember_save_path(saved_path)
        return saved_path

    def load_state(self, path: Path) -> GameState:
        state = self.engine.load_state(path)
        self.monitor.remember_save_path(path)
        self._last_health = self.monitor.evaluate(state, elapsed_time=0.0)
        return state

    def close(self) -> None:
        self.engine.shutdown()
        self._active = False

    def _perform_recovery(self) -> GameState:
        recovery_path = self.monitor.last_save_path
        if recovery_path is None or not recovery_path.exists():
            recovery_path = self.save_state()
        restored_state = self.engine.load_state(recovery_path)
        self.monitor.mark_recovery()
        self._last_health = self.monitor.evaluate(restored_state, elapsed_time=0.0)
        return restored_state

    def _health_payload(self) -> dict[str, object]:
        return self.monitor.health_payload()
