import { createChatPanel } from "./chat.js";
import { createGamePanel } from "./game.js";

export function createApp(root) {
  const container = document.createElement("div");
  container.className = "layout";

  const header = document.createElement("header");
  header.className = "header";
  header.innerHTML = `
    <h1>🧠 IAboy</h1>
    <p>Comparte una partida retro con Gemma 2.</p>
  `;

  const main = document.createElement("main");
  main.className = "content";

  const gamePanel = createGamePanel();
  const chatPanel = createChatPanel();

  gamePanel.addEventListener("session-started", (event) => {
    const { sessionId } = event.detail ?? {};
    if (chatPanel && typeof chatPanel.updateSession === "function") {
      chatPanel.updateSession(sessionId);
    }
  });

  main.appendChild(gamePanel);
  main.appendChild(chatPanel);

  container.appendChild(header);
  container.appendChild(main);
  root.appendChild(container);
}
