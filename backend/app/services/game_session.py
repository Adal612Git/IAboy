"""Abstractions to manage Stable-Retro emulator sessions."""
from __future__ import annotations

import importlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..core.config import get_settings


@dataclass
class ActionSpace:
    """Wrapper that provides a textual representation for emulator actions."""

    buttons: list[str]
    combinations: list[List[int]]

    def to_label(self, action: np.ndarray) -> str:
        active = [name for idx, name in enumerate(self.buttons) if action[idx]]
        return "+".join(active) if active else "NOOP"


@dataclass
class RetroGameSession:
    """Represents a running Gym-Retro environment session."""

    game_id: str
    description_prompt: Optional[str] = None
    frame_skip: int = 4
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        spec = importlib.util.find_spec("retro")
        if spec is None:
            raise RuntimeError(
                "Stable-Retro no está instalado. Instálalo con `pip install stable-retro`."
            )
        retro = importlib.import_module("retro")
        self._env = retro.make(game=self.game_id, use_restricted_actions=retro.Actions.ALL)
        self._last_observation = self._env.reset()
        self._action_space = self._build_action_space()

    def _build_action_space(self) -> ActionSpace:
        buttons = list(self._env.buttons)
        key_map = self._env.get_keys_to_action()
        # Ordenamos las combinaciones para garantizar consistencia entre ejecuciones.
        combinations = [list(key_map[key]) for key in sorted(key_map.keys(), key=lambda item: (len(item), item))]
        if not combinations:
            combinations.append([0 for _ in buttons])
        return ActionSpace(buttons=buttons, combinations=combinations)

    @property
    def action_labels(self) -> list[str]:
        return [self._action_space.to_label(np.array(combo)) for combo in self._action_space.combinations]

    def render_observation(self) -> str:
        """Return a compact textual summary of the current observation."""

        observation = self._last_observation
        if observation is None:
            return "Sin observación disponible."
        mean_pixel = observation.mean()
        metadata = {
            "shape": list(observation.shape),
            "mean_pixel": round(float(mean_pixel), 3),
            "timestamp": time.time(),
        }
        return json.dumps(metadata)

    def step(self, action_index: int) -> dict:
        """Execute one action and update internal state."""

        try:
            action = np.array(self._action_space.combinations[action_index], dtype=np.int8)
        except IndexError as error:
            raise ValueError(f"Índice de acción inválido: {action_index}") from error

        obs, reward, done, info = self._env.step(action)
        for _ in range(self.frame_skip - 1):
            obs, reward, done, info = self._env.step(action)
            if done:
                break
        self._last_observation = obs
        return {
            "observation": self.render_observation(),
            "action_taken": self._action_space.to_label(np.array(action)),
            "reward": float(reward),
            "done": bool(done),
            "info": info,
        }

    def save_state(self, name: Optional[str] = None) -> str:
        """Persist the current emulator state to disk."""

        settings = get_settings()
        filename = name or f"{self.game_id}-{int(time.time())}.state"
        path = settings.save_states_path / filename
        self._env.save_state(str(path))
        return str(path)

    def load_state(self, path: str) -> None:
        self._env.load_state(path)
        self._last_observation = self._env.get_screen()

    def close(self) -> None:
        self._env.close()


class SessionRegistry:
    """Keep track of active sessions and provide lookup helpers."""

    def __init__(self) -> None:
        self._sessions: Dict[str, RetroGameSession] = {}

    def create(self, game_id: str, *, description_prompt: Optional[str] = None) -> RetroGameSession:
        settings = get_settings()
        if game_id not in settings.available_games:
            raise ValueError(f"El juego '{game_id}' no está configurado.")
        session = RetroGameSession(
            game_id=game_id,
            description_prompt=description_prompt,
            frame_skip=settings.frame_skip,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> RetroGameSession:
        if session_id not in self._sessions:
            raise KeyError(f"Sesión '{session_id}' inexistente.")
        return self._sessions[session_id]

    def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.close()

    def list_active(self) -> list[RetroGameSession]:
        return list(self._sessions.values())

    def shutdown(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()


registry = SessionRegistry()
