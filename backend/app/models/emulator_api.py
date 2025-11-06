"""Pydantic models used by the PyBoy emulator REST API."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FramePayload(BaseModel):
    encoding: Literal["base64"] = Field("base64", description="Frame encoding format.")
    data: str = Field(..., description="Base64 encoded frame bytes.")
    shape: List[int] = Field(..., description="Shape of the frame array.")
    dtype: str = Field(..., description="Data type of the frame array.")
    timestamp: float = Field(..., description="Capture timestamp for the frame.")


class GameStatePayload(BaseModel):
    frame: FramePayload
    is_game_over: bool = Field(False, description="Whether the game has reached a terminal state.")
    paused: bool = Field(False, description="Whether the emulator is paused.")
    score: Optional[int] = Field(None, description="Current score value if available.")
    lives: Optional[int] = Field(None, description="Remaining lives if available.")
    progress: Optional[float] = Field(None, description="Progress metric between 0 and 1 if available.")
    step_count: int = Field(..., description="Number of steps executed so far in this session.")
    memory_snapshot: Dict[str, int] = Field(
        default_factory=dict,
        description="Dictionary with sampled memory addresses for debugging and rewards.",
    )


class GameStepResponse(BaseModel):
    state: GameStatePayload
    reward: float
    terminated: bool
    truncated: bool
    info: Dict[str, object] = Field(default_factory=dict)


class StartEmulationRequest(BaseModel):
    rom_path: Optional[str] = Field(
        None,
        description="Relative or absolute path to the ROM to load. If omitted the default ROM is used.",
    )


class StartEmulationResponse(BaseModel):
    session_id: str
    state: GameStatePayload
    action_labels: List[str]
    config: Dict[str, object]


class StepRequest(BaseModel):
    session_id: str
    action: str = Field(..., description="Action label to execute during the step.")


class StepResponse(GameStepResponse):
    session_id: str


class StateResponse(BaseModel):
    session_id: str
    state: GameStatePayload


class ResetRequest(BaseModel):
    session_id: str


class ResetResponse(BaseModel):
    session_id: str
    state: GameStatePayload


class HealthResponse(BaseModel):
    session_id: Optional[str]
    health: Dict[str, object]
    config: Dict[str, object]


class SaveStateResponse(BaseModel):
    session_id: str
    path: str


class LoadStateRequest(BaseModel):
    session_id: str
    path: str


class LoadStateResponse(BaseModel):
    session_id: str
    state: GameStatePayload


class ListSessionsResponse(BaseModel):
    sessions: List[str]
