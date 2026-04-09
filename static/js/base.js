let wwHistory = [];
let wwOpen = false;

function toggleWalletWise() {
    wwOpen = !wwOpen;
    const widget = document.getElementById("wwWidget");
    const icon = document.getElementById("wwButtonIcon");
    if (wwOpen) {
        widget.classList.add("open");
        icon.className = "bi bi-x-lg";
        document.getElementById("wwInput").focus();
    } else {
        widget.classList.remove("open");
        icon.className = "bi bi-stars";
    }
}

function appendMessage(role, text) {
    const messages = document.getElementById("wwMessages");
    const div = document.createElement("div");
    div.className = `ww-msg ${role === "user" ? "ww-user" : "ww-bot"}`;
    div.innerHTML = `<div class="ww-bubble">${text.replace(/\n/g, "<br>")}</div>`;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

function appendTyping() {
    const messages = document.getElementById("wwMessages");
    const div = document.createElement("div");
    div.className = "ww-msg ww-bot ww-typing";
    div.id = "wwTyping";
    div.innerHTML = `<div class="ww-bubble">WalletWise is thinking...</div>`;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function removeTyping() {
    const t = document.getElementById("wwTyping");
    if (t) t.remove();
}

async function sendWWMessage() {
    const input = document.getElementById("wwInput");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    appendMessage("user", message);
    wwHistory.push({ role: "user", content: message });
    appendTyping();

    document.getElementById("wwSendBtn").disabled = true;

    try {
        const response = await fetch("/api/walletwise", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                history: wwHistory.slice(-10)
            })
        });
        const data = await response.json();
        removeTyping();
        const reply = data.reply || "Sorry, I couldn't get a response.";
        appendMessage("bot", reply);
        wwHistory.push({ role: "assistant", content: reply });
    } catch (err) {
        removeTyping();
        appendMessage("bot", "Sorry, something went wrong. Please try again.");
    }

    document.getElementById("wwSendBtn").disabled = false;
    document.getElementById("wwMessages").scrollTop = document.getElementById("wwMessages").scrollHeight;
}

const darkModeToggle = document.getElementById("darkModeToggle");
const darkModeIcon = document.getElementById("darkModeIcon");

function applyDarkMode(enabled) {
    if (enabled) {
        document.documentElement.classList.add("dark-mode-early");
        document.body.classList.add("dark-mode");
        darkModeIcon.className = "bi bi-sun-fill";
    } else {
        document.body.classList.remove("dark-mode");
        document.documentElement.classList.remove("dark-mode-early");
        darkModeIcon.className = "bi bi-moon-fill";
    }
}

const savedMode = localStorage.getItem("darkMode") === "true";
applyDarkMode(savedMode);

darkModeToggle.addEventListener("click", function() {
    const isNowDark = !document.body.classList.contains("dark-mode");
    localStorage.setItem("darkMode", isNowDark);
    applyDarkMode(isNowDark);
});