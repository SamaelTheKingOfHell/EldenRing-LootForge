/**
 * Floating Developer Console Controller [CS-DEBUG]
 * Intercepts, color-codes, and prints all real-time logs and system events.
 */

class DevConsole {
  constructor() {
    this.drawer = document.getElementById("devConsoleDrawer");
    this.toggleBtn = document.getElementById("floatingDevBtn");
    this.body = document.getElementById("consoleBody");
    this.clearBtn = document.getElementById("consoleClearBtn");
    this.copyBtn = document.getElementById("consoleCopyBtn");
    this.debugToggle = document.getElementById("debugModeToggle");
    this.isOpen = false;
    this.pollInterval = null;
    this.lastLogCount = 0;

    this.init();
  }

  init() {
    if (this.toggleBtn) {
      this.toggleBtn.addEventListener("click", () => this.toggle());
    }
    if (this.clearBtn) {
      this.clearBtn.addEventListener("click", () => this.clear());
    }
    if (this.copyBtn) {
      this.copyBtn.addEventListener("click", () => this.copyToClipboard());
    }
    if (this.debugToggle) {
      this.debugToggle.addEventListener("change", (e) => this.setDebugMode(e.target.checked));
    }

    // Start background log polling
    this.startPolling();
  }

  toggle() {
    this.isOpen = !this.isOpen;
    if (this.drawer) {
      this.drawer.classList.toggle("active", this.isOpen);
      if (this.isOpen) {
        this.scrollToBottom();
      }
    }
  }

  startPolling() {
    this.fetchLogs();
    this.pollInterval = setInterval(() => this.fetchLogs(), 1500);
  }

  async fetchLogs() {
    try {
      const res = await fetch("/api/logs?limit=150");
      if (!res.ok) return;
      const data = await res.json();
      const logs = data.logs || [];

      if (logs.length !== this.lastLogCount) {
        this.renderLogs(logs);
        this.lastLogCount = logs.length;
      }

      if (this.debugToggle && data.debug_enabled !== undefined) {
        this.debugToggle.checked = data.debug_enabled;
      }
    } catch (err) {
      // Server may be offline during reboot
    }
  }

  renderLogs(logs) {
    if (!this.body) return;
    const shouldScroll = this.body.scrollTop + this.body.clientHeight >= this.body.scrollHeight - 30;

    this.body.innerHTML = "";
    logs.forEach((log) => {
      const entry = document.createElement("div");
      entry.className = `log-entry ${log.level}`;
      entry.innerHTML = `<span class="log-time">[${log.timestamp.split(" ")[1]}]</span> <span class="log-source">[${log.source}]</span> ${this.escapeHtml(log.message)}`;
      this.body.appendChild(entry);
    });

    if (shouldScroll || this.isOpen) {
      this.scrollToBottom();
    }
  }

  scrollToBottom() {
    if (this.body) {
      this.body.scrollTop = this.body.scrollHeight;
    }
  }

  clear() {
    if (this.body) {
      this.body.innerHTML = '<div class="log-entry INFO">Console cleared.</div>';
    }
    this.lastLogCount = 0;
  }

  copyToClipboard() {
    if (!this.body) return;
    const text = this.body.innerText;
    navigator.clipboard.writeText(text).then(() => {
      alert("Logs copied to clipboard.");
    });
  }

  async setDebugMode(enabled) {
    try {
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ debug_mode: enabled })
      });
    } catch (e) {
      console.error("Failed to update debug mode", e);
    }
  }

  escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.devConsole = new DevConsole();
});
