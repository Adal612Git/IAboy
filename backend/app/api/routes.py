"""API router definition for the IAboy backend."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.config import Settings, get_settings
from ..models.messages import (
    ConversationRequest,
    ConversationResponse,
    CreateSessionRequest,
    LoadStateRequest,
    SaveStateResponse,
    SessionResponse,
    StepRequest,
    StepResponse,
)
from ..services.ai_client import GemmaClient
from ..services.game_session import registry

router = APIRouter()


async def get_gemma_client():
    client = GemmaClient()
    try:
        yield client
    finally:
        await client.close()


@router.get("/health")
def healthcheck(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Simple endpoint used by the frontend to verify server status."""

    return {"status": "ok", "model": settings.ollama_model}


@router.get("/games")
def list_games(settings: Settings = Depends(get_settings)) -> dict[str, list[str]]:
    return {"games": settings.available_games}


@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: CreateSessionRequest) -> SessionResponse:
    try:
        session = registry.create(
            game_id=payload.game_id,
            description_prompt=payload.description_prompt,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return SessionResponse(session_id=session.session_id, game_id=session.game_id, mode=payload.mode)


@router.post("/sessions/{session_id}/step", response_model=StepResponse)
async def step_session(
    session_id: str,
    payload: StepRequest,
    client: GemmaClient = Depends(get_gemma_client),
) -> StepResponse:
    try:
        session = registry.get(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    action_label = payload.player_action
    if payload.use_ai:
        prompt = _build_action_prompt(
            observation_summary=session.render_observation(),
            action_labels=session.action_labels,
            game_id=session.game_id,
            player_action=payload.player_action,
        )
        action_label = await client.generate_action(prompt)

    if action_label is None:
        raise HTTPException(status_code=400, detail="No hay acción definida para ejecutar.")

    action_index = _resolve_action_index(action_label, session)
    try:
        result = session.step(action_index)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return StepResponse(**result)


@router.post("/sessions/{session_id}/save", response_model=SaveStateResponse)
def save_session_state(session_id: str) -> SaveStateResponse:
    try:
        session = registry.get(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    path = session.save_state()
    return SaveStateResponse(success=True, path=path)


@router.post("/sessions/{session_id}/load", response_model=SaveStateResponse)
def load_session_state(session_id: str, payload: LoadStateRequest) -> SaveStateResponse:
    try:
        session = registry.get(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    session.load_state(payload.path)
    return SaveStateResponse(success=True, path=payload.path)


@router.post("/sessions/{session_id}/chat", response_model=ConversationResponse)
async def chat_with_ai(
    session_id: str,
    payload: ConversationRequest,
    client: GemmaClient = Depends(get_gemma_client),
) -> ConversationResponse:
    try:
        registry.get(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    formatted_messages = [message.dict() for message in payload.messages]
    reply = await client.generate_chat_reply(formatted_messages)
    return ConversationResponse(reply=reply)


def _resolve_action_index(action_label: str, session) -> int:
    try:
        return session.action_labels.index(action_label)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"Acción desconocida: {action_label}") from error


def _build_action_prompt(
    *,
    observation_summary: str,
    action_labels: list[str],
    game_id: str,
    player_action: str | None,
) -> str:
    base_prompt = (
        "Eres Gemma 2, un jugador cooperativo que participa en juegos retro junto a un humano. "
        "Debes responder con una acción válida del controlador usando el mismo formato devuelto por la API."
    )
    details = [
        f"Observación: {observation_summary}",
        f"Acciones disponibles: {', '.join(action_labels)}",
        f"Juego actual: {game_id}",
    ]
    if player_action:
        details.append(f"El humano sugiere: {player_action}")
    return "\n".join([base_prompt, *details])
