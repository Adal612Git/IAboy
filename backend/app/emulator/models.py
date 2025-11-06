"""Core data models shared across the emulation subsystem."""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, MutableMapping, Optional

import numpy as np


@dataclass
class FrameEnvelope:
    """Holds a raw frame and metadata required for serialisation."""

    pixels: np.ndarray
    timestamp: float = field(default_factory=lambda: time.time())

    def validate(self, expected_shape: Optional[Iterable[int]] = None) -> None:
        """Ensure the frame contains valid data before it is returned to clients."""

        if not isinstance(self.pixels, np.ndarray):
            raise TypeError("Frame data must be a numpy.ndarray instance.")
        if self.pixels.ndim not in (2, 3):
            raise ValueError("Frames must be 2D (grayscale) or 3D (RGB) arrays.")
        if expected_shape and tuple(expected_shape) != tuple(self.pixels.shape):
            raise ValueError(
                f"Unexpected frame shape {self.pixels.shape}; expected {tuple(expected_shape)}."
            )

    def as_base64(self) -> str:
        """Return the frame encoded as base64 so it can be sent via JSON."""

        return base64.b64encode(self.pixels.tobytes()).decode("ascii")

    def describe(self) -> Dict[str, object]:
        """Return structured metadata for logging and health reports."""

        return {
            "timestamp": self.timestamp,
            "shape": list(self.pixels.shape),
            "dtype": str(self.pixels.dtype),
        }


@dataclass
class GameState:
    """Full snapshot of the emulator at a given step."""

    frame: FrameEnvelope
    is_game_over: bool = False
    paused: bool = False
    score: Optional[int] = None
    lives: Optional[int] = None
    progress: Optional[float] = None
    step_count: int = 0
    memory_snapshot: Mapping[str, int] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, object]:
        """Convert the state into a JSON serialisable payload."""

        return {
            "frame": {
                "encoding": "base64",
                "data": self.frame.as_base64(),
                "shape": list(self.frame.pixels.shape),
                "dtype": str(self.frame.pixels.dtype),
                "timestamp": self.frame.timestamp,
            },
            "is_game_over": self.is_game_over,
            "paused": self.paused,
            "score": self.score,
            "lives": self.lives,
            "progress": self.progress,
            "step_count": self.step_count,
            "memory_snapshot": dict(self.memory_snapshot),
        }


@dataclass
class GameStepResult:
    """Result returned after executing a step in the emulator."""

    new_state: GameState
    reward: float
    terminated: bool
    truncated: bool
    info: MutableMapping[str, object] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, object]:
        payload = {
            "state": self.new_state.to_payload(),
            "reward": self.reward,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "info": dict(self.info),
        }
        return payload


@dataclass
class HealthStatus:
    """Represents the outcome of a health check evaluation."""

    healthy: bool
    issues: Iterable[str] = field(default_factory=tuple)
    consecutive_failures: int = 0
    needs_recovery: bool = False
    last_checked: float = field(default_factory=lambda: time.time())
    metrics: Mapping[str, object] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, object]:
        return {
            "healthy": self.healthy,
            "issues": list(self.issues),
            "consecutive_failures": self.consecutive_failures,
            "needs_recovery": self.needs_recovery,
            "last_checked": self.last_checked,
            "metrics": dict(self.metrics),
        }


@dataclass
class MetricsAccumulator:
    """Helper to store runtime metrics for observability endpoints."""

    total_steps: int = 0
    total_failures: int = 0
    total_recoveries: int = 0
    frame_times: list[float] = field(default_factory=list)

    def register_step(self, duration: float) -> None:
        self.total_steps += 1
        self.frame_times.append(duration)

    def register_failure(self) -> None:
        self.total_failures += 1

    def register_recovery(self) -> None:
        self.total_recoveries += 1

    def summary(self) -> Dict[str, object]:
        if self.frame_times:
            mean_frame_time = float(np.mean(self.frame_times))
            max_frame_time = float(np.max(self.frame_times))
            min_frame_time = float(np.min(self.frame_times))
        else:
            mean_frame_time = max_frame_time = min_frame_time = 0.0
        return {
            "total_steps": self.total_steps,
            "total_failures": self.total_failures,
            "total_recoveries": self.total_recoveries,
            "mean_frame_time": mean_frame_time,
            "max_frame_time": max_frame_time,
            "min_frame_time": min_frame_time,
        }
