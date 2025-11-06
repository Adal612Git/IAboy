"""FastAPI routes exposing the PyBoy emulator backend."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.config import Settings, get_settings
from ..emulator import EmulatorManager, build_emulator_config
from ..emulator.session import EmulatorSession
from ..models.emulator_api import (
    GameStatePayload,
    HealthResponse,
    ListSessionsResponse,
    LoadStateRequest,
    LoadStateResponse,
    ResetRequest,
    ResetResponse,
    SaveStateResponse,
    StartEmulationRequest,
    StartEmulationResponse,
    StateResponse,
    StepRequest,
    StepResponse,
)

router = APIRouter()


@lru_cache()
def _build_manager(settings: Settings) -> EmulatorManager:
    config = build_emulator_config(settings)
    return EmulatorManager(config)


def get_manager(settings: Settings = Depends(get_settings)) -> EmulatorManager:
    return _build_manager(settings)


@router.post("/start", response_model=StartEmulationResponse)
def start_emulation(
    payload: StartEmulationRequest,
    manager: EmulatorManager = Depends(get_manager),
) -> StartEmulationResponse:
    session = manager.start_session(payload.rom_path)
    state_payload = _to_state_payload(session.current_state())
    response = StartEmulationResponse(
        session_id=session.session_id,
        state=state_payload,
        action_labels=list(session.action_labels),
        config=session.config.to_dict(),
    )
    return response


@router.post("/step", response_model=StepResponse)
def step_emulation(
    payload: StepRequest,
    manager: EmulatorManager = Depends(get_manager),
) -> StepResponse:
    session = _get_session(manager, payload.session_id)
    try:
        result = session.step(payload.action)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    response = StepResponse(session_id=session.session_id, **result.to_payload())
    return response


@router.get("/state", response_model=StateResponse)
def get_state(
    session_id: str = Query(..., description="Identifier of the emulator session."),
    manager: EmulatorManager = Depends(get_manager),
) -> StateResponse:
    session = _get_session(manager, session_id)
    state_payload = _to_state_payload(session.current_state())
    return StateResponse(session_id=session.session_id, state=state_payload)


@router.post("/reset", response_model=ResetResponse)
def reset_session(
    payload: ResetRequest,
    manager: EmulatorManager = Depends(get_manager),
) -> ResetResponse:
    session = _get_session(manager, payload.session_id)
    state = session.reset()
    return ResetResponse(session_id=session.session_id, state=_to_state_payload(state))


@router.get("/health", response_model=HealthResponse)
def get_health(
    session_id: Optional[str] = Query(
        None,
        description="When provided returns health metrics for a specific session."
        " Otherwise returns global configuration data.",
    ),
    manager: EmulatorManager = Depends(get_manager),
) -> HealthResponse:
    if session_id:
        session = _get_session(manager, session_id)
        return HealthResponse(
            session_id=session.session_id,
            health=session.current_health(),
            config=session.config.to_dict(),
        )
    return HealthResponse(
        session_id=None,
        health={"status": "ok"},
        config=manager.config.to_dict(),
    )


@router.post("/save", response_model=SaveStateResponse)
def save_state(
    payload: ResetRequest,
    manager: EmulatorManager = Depends(get_manager),
) -> SaveStateResponse:
    session = _get_session(manager, payload.session_id)
    path = session.save_state()
    return SaveStateResponse(session_id=session.session_id, path=str(path))


@router.post("/load", response_model=LoadStateResponse)
def load_state(
    payload: LoadStateRequest,
    manager: EmulatorManager = Depends(get_manager),
) -> LoadStateResponse:
    session = _get_session(manager, payload.session_id)
    rom_path = Path(payload.path)
    if not rom_path.exists():
        raise HTTPException(status_code=404, detail=f"El archivo {rom_path} no existe.")
    state = session.load_state(rom_path)
    return LoadStateResponse(
        session_id=session.session_id,
        state=_to_state_payload(state),
    )


@router.get("/sessions", response_model=ListSessionsResponse)
def list_sessions(manager: EmulatorManager = Depends(get_manager)) -> ListSessionsResponse:
    return ListSessionsResponse(sessions=[session.session_id for session in manager.list_sessions()])


def _get_session(manager: EmulatorManager, session_id: str) -> EmulatorSession:
    try:
        return manager.get_session(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _to_state_payload(state) -> GameStatePayload:
    return GameStatePayload.parse_obj(state.to_payload())
