"""Health monitoring and recovery helpers for the PyBoy backend."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from .config import EmulatorConfig
from .models import GameState, HealthStatus, MetricsAccumulator


class HealthMonitor:
    """Continuously validates the emulator output and coordinates recoveries."""

    def __init__(self, config: EmulatorConfig) -> None:
        self.config = config
        self._consecutive_failures = 0
        self._metrics = MetricsAccumulator()
        self._last_state: Optional[GameState] = None
        self._last_save_path: Optional[Path] = None
        self._last_health_status: Optional[HealthStatus] = None
        self._last_check_step = 0

    # ------------------------------------------------------------------
    # Properties and basic helpers
    # ------------------------------------------------------------------
    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def metrics(self) -> MetricsAccumulator:
        return self._metrics

    @property
    def last_state(self) -> Optional[GameState]:
        return self._last_state

    @property
    def last_health_status(self) -> Optional[HealthStatus]:
        return self._last_health_status

    @property
    def last_save_path(self) -> Optional[Path]:
        return self._last_save_path

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._metrics = MetricsAccumulator()
        self._last_state = None
        self._last_save_path = None
        self._last_health_status = None
        self._last_check_step = 0

    # ------------------------------------------------------------------
    # Health evaluation
    # ------------------------------------------------------------------
    def should_run_check(self, step_count: int) -> bool:
        return step_count == 0 or (
            step_count - self._last_check_step
        ) >= self.config.health_check_interval_steps

    def evaluate(self, state: GameState, *, elapsed_time: float) -> HealthStatus:
        issues: list[str] = []
        try:
            state.frame.validate(self.config.frame_dimensions)
        except Exception as exc:  # pragma: no cover - exercised in failure tests
            issues.append(str(exc))
        if not isinstance(state.frame.pixels, np.ndarray):
            issues.append("Frame data is not a numpy array.")
        elif state.frame.pixels.size == 0:
            issues.append("Frame array is empty.")
        healthy = not issues

        if healthy:
            self._consecutive_failures = 0
            self._metrics.register_step(elapsed_time)
        else:
            self._consecutive_failures += 1
            self._metrics.register_failure()

        status = HealthStatus(
            healthy=healthy,
            issues=issues,
            consecutive_failures=self._consecutive_failures,
            needs_recovery=self._consecutive_failures >= self.config.max_consecutive_health_failures,
            metrics=self._metrics.summary(),
        )
        self._last_state = state
        self._last_health_status = status
        self._last_check_step = state.step_count
        return status

    # ------------------------------------------------------------------
    # Recovery coordination
    # ------------------------------------------------------------------
    def mark_recovery(self) -> None:
        self._metrics.register_recovery()
        self._consecutive_failures = 0

    def remember_save_path(self, path: Path) -> None:
        self._last_save_path = path

    def health_payload(self) -> dict[str, object]:
        status_payload = self._last_health_status.to_payload() if self._last_health_status else {}
        payload = {
            "status": status_payload,
            "metrics": self._metrics.summary(),
        }
        if self._last_state:
            payload["last_state"] = {
                "step_count": self._last_state.step_count,
                "timestamp": self._last_state.frame.timestamp,
                "score": self._last_state.score,
            }
        if self._last_save_path:
            payload["last_save_path"] = str(self._last_save_path)
        return payload
