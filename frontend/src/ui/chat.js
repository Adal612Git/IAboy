import axios from "axios";

export function createChatPanel() {
  const section = document.createElement("section");
  section.className = "panel chat-panel";

  const header = document.createElement("h2");
  header.textContent = "Chat";

  const messagesList = document.createElement("div");
  messagesList.className = "chat-messages";

  const form = document.createElement("form");
  form.className = "chat-input";

  const textarea = document.createElement("textarea");
  textarea.placeholder = "Habla con Gemma 2...";
  textarea.required = true;

  const sendButton = document.createElement("button");
  sendButton.type = "submit";
  sendButton.textContent = "Enviar";

  let conversation = [];
  let sessionId = null;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!textarea.value.trim() || !sessionId) {
      return;
    }
    const userMessage = { role: "user", content: textarea.value.trim() };
    conversation = [...conversation, userMessage];
    appendMessage(messagesList, "👤", userMessage.content);
    textarea.value = "";

    try {
      const response = await axios.post(`/api/sessions/${sessionId}/chat`, {
        messages: conversation,
      });
      const reply = response.data.reply ?? "";
      conversation = [...conversation, { role: "assistant", content: reply }];
      appendMessage(messagesList, "🤖", reply);
    } catch (error) {
      appendMessage(messagesList, "⚠️", `Error al contactar a Gemma: ${error.message}`);
    }
  });

  section.append(header, messagesList, form);
  form.append(textarea, sendButton);

  appendMessage(messagesList, "ℹ️", "Inicia un juego para activar la conversación con Gemma 2.");

  section.updateSession = (id) => {
    sessionId = id;
    conversation = [];
    messagesList.innerHTML = "";
    appendMessage(messagesList, "ℹ️", "La sesión está lista para conversar.");
  };

  return section;
}

function appendMessage(container, prefix, text) {
  const message = document.createElement("p");
  message.innerHTML = `<span>${prefix}</span> ${text}`;
  container.appendChild(message);
  container.scrollTop = container.scrollHeight;
}
