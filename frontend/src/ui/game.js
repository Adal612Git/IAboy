import axios from "axios";

export function createGamePanel() {
  const section = document.createElement("section");
  section.className = "panel game-panel";

  const header = document.createElement("div");
  header.className = "game-header";

  const title = document.createElement("h2");
  title.textContent = "Juego";

  const status = document.createElement("p");
  status.className = "status";
  status.textContent = "Sin sesión activa";

  header.append(title, status);

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 448;
  canvas.className = "game-canvas";

  const controls = document.createElement("div");
  controls.className = "controls";

  const select = document.createElement("select");
  select.className = "game-select";

  const startButton = document.createElement("button");
  startButton.textContent = "Iniciar";

  const stepButton = document.createElement("button");
  stepButton.textContent = "Avanzar";
  stepButton.disabled = true;

  const aiToggle = document.createElement("label");
  aiToggle.className = "toggle";
  aiToggle.innerHTML = `
    <input type="checkbox" />
    <span>Usar IA</span>
  `;

  controls.append(select, startButton, stepButton, aiToggle);

  section.append(header, canvas, controls);

  drawText(canvas, "Selecciona un juego y presiona Iniciar para comenzar.");

  let sessionId = null;
  let useAi = false;

  aiToggle.querySelector("input").addEventListener("change", (event) => {
    useAi = event.target.checked;
  });

  startButton.addEventListener("click", async () => {
    const gameId = select.value;
    if (!gameId) {
      return;
    }
    try {
      const response = await axios.post("/api/sessions", {
        game_id: gameId,
        mode: "coop",
      });
      sessionId = response.data.session_id;
      status.textContent = `Sesión activa: ${gameId}`;
      stepButton.disabled = false;
      section.dispatchEvent(new CustomEvent("session-started", { detail: { sessionId } }));
    } catch (error) {
      status.textContent = `Error al iniciar: ${error.message}`;
    }
  });

  stepButton.addEventListener("click", async () => {
    if (!sessionId) {
      return;
    }
    try {
      const response = await axios.post(`/api/sessions/${sessionId}/step`, {
        use_ai: useAi,
      });
      const { observation, reward, action_taken } = response.data;
      drawText(canvas, `Acción: ${action_taken}\nRecompensa: ${reward}\nObs: ${observation}`);
    } catch (error) {
      status.textContent = `Error al avanzar: ${error.message}`;
    }
  });

  fetchGames(select);

  return section;
}

async function fetchGames(select) {
  try {
    const response = await axios.get("/api/games");
    select.innerHTML = "";
    response.data.games.forEach((gameId) => {
      const option = document.createElement("option");
      option.value = gameId;
      option.textContent = gameId;
      select.appendChild(option);
    });
  } catch (error) {
    const option = document.createElement("option");
    option.textContent = "Error al cargar juegos";
    select.appendChild(option);
  }
}

function drawText(canvas, text) {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }
  context.fillStyle = "#0b0c10";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#66fcf1";
  context.font = "16px monospace";
  const lines = text.split("\n");
  lines.forEach((line, index) => {
    context.fillText(line, 12, 28 + index * 22);
  });
}
