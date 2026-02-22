const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatWindow = document.getElementById("chatWindow");
const modelSelect = document.getElementById("modelSelect");
const apiKeyInput = document.getElementById("apiKeyInput");
const apiKeyStatus = document.getElementById("apiKeyStatus");
const sendButton = chatForm.querySelector("button[type='submit']");
const container = document.querySelector(".container");

const messages = [
  {
    role: "system",
    content: "You are a helpful assistant. Keep responses concise.",
  },
];

const updateSendButtonState = () => {
  const isValid =
    apiKeyStatus.style.color === "rgb(16, 185, 129)" &&
    apiKeyStatus.textContent === "✓ Valid";
  sendButton.disabled = !isValid;
};

const validateApiKey = async () => {
  const key = apiKeyInput.value.trim();
  if (!key) {
    apiKeyStatus.textContent = "";
    updateSendButtonState();
    return false;
  }

  // Show validating status
  apiKeyStatus.textContent = "Validating...";
  apiKeyStatus.style.color = "#f59e0b";
  updateSendButtonState();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "llama-3.3-70b-versatile",
        messages: [{ role: "system", content: "test" }],
        api_key: key,
        max_tokens: 10,
      }),
    });

    if (response.ok) {
      apiKeyStatus.textContent = "✓ Valid";
      apiKeyStatus.style.color = "#10b981";
      updateSendButtonState();
      return true;
    } else {
      apiKeyStatus.textContent = "✗ Invalid";
      apiKeyStatus.style.color = "#ef4444";
      updateSendButtonState();
      return false;
    }
  } catch (error) {
    apiKeyStatus.textContent = "✗ Error";
    apiKeyStatus.style.color = "#ef4444";
    updateSendButtonState();
    return false;
  }
};

apiKeyInput.addEventListener("blur", validateApiKey);
// Also validate on input for real-time feedback
apiKeyInput.addEventListener("input", () => {
  if (!apiKeyInput.value.trim()) {
    apiKeyStatus.textContent = "";
    updateSendButtonState();
  }
});

const updateLayoutState = () => {
  const hasUserMessages = messages.some((m) => m.role === "user");
  if (hasUserMessages) {
    container.classList.add("expanded");
  } else {
    container.classList.remove("expanded");
  }
};

const addMessage = (role, content) => {
  const message = document.createElement("div");
  message.className = `message ${role}`;

  // Add avatar for both user and assistant
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "assistant" ? "🤖" : "👤";
  message.appendChild(avatar);

  // Add message bubble
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  const text = document.createElement("p");
  text.textContent = content;
  bubble.appendChild(text);
  message.appendChild(bubble);

  chatWindow.appendChild(message);
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
