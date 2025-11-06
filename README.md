# 🧠 IAboy

IAboy es un experimento que combina emulación retro, un asistente conversacional local (Gemma 2 vía Ollama) y una interfaz web colaborativa. El objetivo es permitir que una persona juegue títulos clásicos mientras conversa con la IA y comparte los controles del juego.

## Arquitectura

```
Frontend (Vite) ←→ FastAPI Backend ←→ Stable-Retro ←→ Gemma 2 (Ollama)
                                   ↓
                             Sistema de recompensas
                                   ↓
                         Decisiones de la IA en tiempo real
```

### Componentes principales

| Componente | Descripción |
| ---------- | ----------- |
| **FastAPI** | Expone endpoints REST para gestionar sesiones, chat y control del emulador. |
| **Stable-Retro** | Provee el entorno de emulación compatible con múltiples consolas retro. |
| **Gemma 2** | Modelo de lenguaje local que dialoga y decide acciones dentro del juego. |
| **Frontend** | Interfaz web con un lienzo para el juego y un chat en vivo. |

## Backend

El backend vive en [`backend/app`](backend/app) y ofrece endpoints para:

- Crear y listar sesiones de juego.
- Avanzar el estado de la emulación solicitando decisiones a Gemma 2 si es necesario.
- Guardar estados del juego.
- Mantener conversaciones en paralelo con la IA.

Arranque local:

```bash
cd backend
uvicorn app.main:app --reload
```

### Variables de entorno

Se pueden configurar a través de un archivo `.env` en la raíz del proyecto:

```
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:9b
ROMS_PATH=~/retro/roms
SAVE_STATES_PATH=~/retro/save_states
FRAME_SKIP=4
```

## Frontend

El frontend es un prototipo ligero construido con Vite (sin framework). Incluye un lienzo donde se muestran los resultados del entorno y un panel de chat que se conecta a los endpoints REST.

Para ejecutarlo:

```bash
cd frontend
npm install
npm run dev
```

Durante el desarrollo se configura un proxy local hacia `http://localhost:8000` para acceder al backend.

## Flujo de trabajo esperado

1. El usuario abre la interfaz web y selecciona un juego.
2. El backend inicia una sesión de Stable-Retro para ese ROM.
3. Cada paso puede ejecutarse manualmente o delegarse a Gemma 2, que responde con la acción a realizar.
4. El estado del juego se refleja en el lienzo (por ahora se muestra un resumen textual como placeholder).
5. El chat permite mantener una conversación contextualizada con la IA.

## Próximos pasos sugeridos

- Integrar streaming de vídeo en tiempo real desde Stable-Retro al frontend.
- Implementar WebSockets para actualizaciones continuas del juego y del chat.
- Diseñar un sistema de recompensas configurable y métricas de progreso.
- Añadir soporte multijugador real (humano + IA) mapeando múltiples controladores.
