"""Session registry and orchestration helpers."""
from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional

from .config import EmulatorConfig
from .engine import PyBoyEngine
from .monitor import HealthMonitor
from .session import EmulatorSession

EngineFactory = Callable[[EmulatorConfig], PyBoyEngine]
MonitorFactory = Callable[[EmulatorConfig], HealthMonitor]


def _default_engine_factory(config: EmulatorConfig) -> PyBoyEngine:
    return PyBoyEngine(config)


def _default_monitor_factory(config: EmulatorConfig) -> HealthMonitor:
    return HealthMonitor(config)


class EmulatorManager:
    """High level orchestrator that keeps track of emulator sessions."""

    def __init__(
        self,
        config: EmulatorConfig,
        *,
        engine_factory: Optional[EngineFactory] = None,
        monitor_factory: Optional[MonitorFactory] = None,
    ) -> None:
        self.config = config
        self._engine_factory = engine_factory or _default_engine_factory
        self._monitor_factory = monitor_factory or _default_monitor_factory
        self._sessions: Dict[str, EmulatorSession] = {}

    def start_session(self, rom_reference: Optional[str]) -> EmulatorSession:
        session = EmulatorSession(
            config=self.config,
            engine=self._engine_factory(self.config),
            monitor=self._monitor_factory(self.config),
        )
        session.start(rom_reference)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> EmulatorSession:
        if session_id not in self._sessions:
            raise KeyError(f"Sesión '{session_id}' inexistente.")
        return self._sessions[session_id]

    def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.close()

    def list_sessions(self) -> Iterable[EmulatorSession]:
        return list(self._sessions.values())

    def shutdown(self) -> None:
        for session in list(self._sessions.values()):
            session.close()
        self._sessions.clear()
