const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatWindow = document.getElementById("chatWindow");
const modelSelect = document.getElementById("modelSelect");
const apiKeyInput = document.getElementById("apiKeyInput");
const container = document.querySelector(".container");

const messages = [
  {
    role: "system",
    content: "You are a helpful assistant. Keep responses concise.",
  },
];

const updateLayoutState = () => {
  const hasUserMessages = messages.some((m) => m.role === "user");
  if (hasUserMessages) {
    container.classList.add("expanded");
  } else {
    container.classList.remove("expanded");
  }
};

const addMessage = (role, content) => {
  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;
  const text = document.createElement("p");
  text.textContent = content;
  bubble.appendChild(text);
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
};

const sendMessage = async (userText) => {
  const payload = {
    model: modelSelect.value,
    messages: [...messages, { role: "user", content: userText }],
    max_tokens: 250,
    temperature: 0.7,
  };

  const apiKey = apiKeyInput.value.trim();
  if (apiKey) {
    payload.api_key = apiKey;
  }

  const response = await fetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    try {
      const errorData = JSON.parse(errorText);
      throw new Error(errorData.detail || errorText);
    } catch (e) {
      throw new Error(errorText || `Error ${response.status}`);
    }
  }

  const data = await response.json();
  return data.reply;
};

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userText = chatInput.value.trim();
  if (!userText) return;

  addMessage("user", userText);
  messages.push({ role: "user", content: userText });
  updateLayoutState();
  chatInput.value = "";

  try {
    const reply = await sendMessage(userText);
    messages.push({ role: "assistant", content: reply });
    addMessage("assistant", reply);
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
    console.error(error);
  }
});
