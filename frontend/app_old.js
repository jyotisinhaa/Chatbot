const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatWindow = document.getElementById("chatWindow");
const modelSelect = document.getElementById("modelSelect");
const apiKeyInput = document.getElementById("apiKeyInput");
const apiKeyStatus = document.getElementById("apiKeyStatus");
const sendButton = chatForm.querySelector("button[type='submit']");
const container = document.querySelector(".container");

// Session ID for backend context management
let sessionId = null;
let hasUserMessages = false;

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
        message: "test",
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

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userText = chatInput.value.trim();
  if (!userText) return;

  addMessage("user", userText);
  hasUserMessages = true;
  updateLayoutState();
  chatInput.value = "";

  try {
    const reply = await sendMessage(userText);
    addMessage("assistant", reply);
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
    console.error(error);
  }
});

// Dark mode toggle functionality
console.log("=== Script loaded, initializing theme toggle ===");

function initializeThemeToggle() {
  console.log("→ initializeThemeToggle() called");

  // Get elements
  const themeToggle = document.getElementById("themeToggle");
  const themeIcon = document.getElementById("themeIcon");
  const html = document.documentElement;

  console.log("→ Elements found:", {
    themeToggle: themeToggle !== null,
    themeIcon: themeIcon !== null,
    html: html !== null,
  });

  if (!themeToggle || !themeIcon) {
    console.error("✗ CRITICAL: Theme toggle elements not found!");
    console.error("  themeToggle:", themeToggle);
    console.error("  themeIcon:", themeIcon);

    // Try to find them manually
    console.log(
      "  Searching for #themeToggle:",
      document.querySelector("#themeToggle"),
    );
    console.log(
      "  Searching for #themeIcon:",
      document.querySelector("#themeIcon"),
    );
    return;
  }

  console.log("✓ Both elements found successfully!");

  // Set theme function
  function setTheme(theme) {
    console.log(`→ Setting theme: ${theme}`);
    html.setAttribute("data-theme", theme);
    themeToggle.classList.toggle("active", theme === "dark");
    themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
    localStorage.setItem("theme", theme);
    console.log(
      `✓ Theme set. data-theme="${html.getAttribute("data-theme")}", active="${themeToggle.classList.contains("active")}"`,
    );
  }

  // Get initial theme
  function initializeTheme() {
    const savedTheme = localStorage.getItem("theme");
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;
    const theme = savedTheme ? savedTheme : prefersDark ? "dark" : "light";

    console.log(
      `→ Initializing theme: saved="${savedTheme}", prefersDark=${prefersDark}, using="${theme}"`,
    );
    setTheme(theme);
  }

  // Add click handler
  console.log("→ Adding click handler to button...");

  function handleClick(e) {
    console.log("★ BUTTON CLICKED!");
    const currentTheme = html.getAttribute("data-theme") || "light";
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    console.log(`→ Switching from "${currentTheme}" to "${newTheme}"`);
    setTheme(newTheme);
  }

  themeToggle.addEventListener("click", handleClick);

  console.log("✓ Click handlers attached");

  // System preference changes
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function (e) {
      if (!localStorage.getItem("theme")) {
        const theme = e.matches ? "dark" : "light";
        setTheme(theme);
      }
    });

  // Initialize
  initializeTheme();
  console.log("✓✓✓ Theme toggle initialization complete! ✓✓✓");
}

// Call immediately
initializeThemeToggle();
