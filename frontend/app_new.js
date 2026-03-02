// Get DOM elements
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");
const chatContainer = document.getElementById("chatContainer");
const modelSelect = document.getElementById("modelSelect");
const apiKeyInput = document.getElementById("apiKeyInput");
const apiKeyStatus = document.getElementById("apiKeyStatus");
const sendButton = document.getElementById("sendButton");
const sidebar = document.getElementById("sidebar");
const menuToggle = document.getElementById("menuToggle");
const newChatBtn = document.getElementById("newChatBtn");
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");
const themeText = document.getElementById("themeText");

// Session management
let sessionId = null;

// Auto-resize textarea
chatInput.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";
});

// Sidebar toggle
menuToggle.addEventListener("click", () => {
  sidebar.classList.toggle("hidden");
});

// New chat button
newChatBtn.addEventListener("click", () => {
  sessionId = null;
  chatMessages.innerHTML = `
    <div class="message assistant">
      <div class="message-avatar">🤖</div>
      <div class="message-content">
        Hello! How can I assist you today?
      </div>
    </div>
  `;
});

// Theme toggle
function setTheme(isDark) {
  document.documentElement.setAttribute(
    "data-theme",
    isDark ? "dark" : "light",
  );
  themeIcon.textContent = isDark ? "☀️" : "🌙";
  themeText.textContent = isDark ? "Light Mode" : "Dark Mode";
  localStorage.setItem("theme", isDark ? "dark" : "light");
}

// Initialize theme
const savedTheme = localStorage.getItem("theme");
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
const isDark = savedTheme ? savedTheme === "dark" : prefersDark;
setTheme(isDark);

themeToggle.addEventListener("click", () => {
  const currentTheme = document.documentElement.getAttribute("data-theme");
  setTheme(currentTheme !== "dark");
});

// API Key validation
const updateSendButtonState = () => {
  const hasApiKey = apiKeyInput.value.trim().length > 0;
  const isValid = apiKeyStatus.classList.contains("valid");
  sendButton.disabled = !hasApiKey || !isValid;
};

const validateApiKey = async () => {
  const key = apiKeyInput.value.trim();
  if (!key) {
    apiKeyStatus.textContent = "";
    apiKeyStatus.className = "api-status";
    updateSendButtonState();
    return false;
  }

  // Show validating status
  apiKeyStatus.textContent = "⏳ Validating...";
  apiKeyStatus.className = "api-status validating";
  updateSendButtonState();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "llama-3.3-70b-versatile",
        message: "test",
        api_key: key,
        max_tokens: 10,
      }),
    });

    if (response.ok) {
      apiKeyStatus.textContent = "✓ Valid";
      apiKeyStatus.className = "api-status valid";
      updateSendButtonState();
      return true;
    } else {
      apiKeyStatus.textContent = "✗ Invalid";
      apiKeyStatus.className = "api-status invalid";
      updateSendButtonState();
      return false;
    }
  } catch (error) {
    apiKeyStatus.textContent = "✗ Error";
    apiKeyStatus.className = "api-status invalid";
    updateSendButtonState();
    return false;
  }
};

apiKeyInput.addEventListener("blur", validateApiKey);
apiKeyInput.addEventListener("input", () => {
  if (!apiKeyInput.value.trim()) {
    apiKeyStatus.textContent = "";
    apiKeyStatus.className = "api-status";
    updateSendButtonState();
  }
});

// Add message to chat
const addMessage = (role, content) => {
  const message = document.createElement("div");
  message.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "assistant" ? "🤖" : "👤";

  const messageContent = document.createElement("div");
  messageContent.className = "message-content";
  messageContent.textContent = content;

  message.appendChild(avatar);
  message.appendChild(messageContent);
  chatMessages.appendChild(message);

  // Scroll to bottom
  chatContainer.scrollTop = chatContainer.scrollHeight;
};

// Send message to API
const sendMessage = async (userText) => {
  const payload = {
    model: modelSelect.value,
    message: userText,
    max_tokens: 250,
    temperature: 0.7,
  };

  const apiKey = apiKeyInput.value.trim();
  if (apiKey) {
    payload.api_key = apiKey;
  }

  // Include session_id if we have one
  if (sessionId) {
    payload.session_id = sessionId;
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
  // Store session_id from response
  sessionId = data.session_id;
  return data.reply;
};

// Handle form submission
chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userText = chatInput.value.trim();
  if (!userText) return;

  addMessage("user", userText);
  chatInput.value = "";
  chatInput.style.height = "auto";

  try {
    const reply = await sendMessage(userText);
    addMessage("assistant", reply);
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
    console.error(error);
  }
});

// Allow Enter to send, Shift+Enter for new line
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});
