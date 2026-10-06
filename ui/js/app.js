/**
 * LootForge Main Frontend Controller
 * Implements i18n localization [CS-LOCALIZATION], mod scanner interaction,
 * review table configuration, and forge execution.
 */

class LootForgeApp {
  constructor() {
    this.currentLocale = "en";
    this.strings = {};
    this.options = {
      boss_remembrances: [],
      elite_enemies: [],
      merchants: []
    };
    this.scannedSets = [];
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.loadLocalization(this.currentLocale);
    await this.loadOptions();
    await this.refreshStatus();
    await this.scanMods();
  }

  bindEvents() {
    // Language switcher
    const langSelect = document.getElementById("langSelect");
    if (langSelect) {
      langSelect.addEventListener("change", (e) => this.loadLocalization(e.target.value));
    }

    // Active Regulation Path input
    const activeRegInput = document.getElementById("activeRegInput");
    if (activeRegInput) {
      activeRegInput.addEventListener("change", (e) => {
        this.updateConfig({ active_regulation_path: e.target.value.trim() });
      });
    }

    // Quick toggle: Use Mod Engine Regulation
    const useModRegBtn = document.getElementById("useModRegBtn");
    if (useModRegBtn) {
      useModRegBtn.addEventListener("click", () => {
        const path = "mod/regulation.bin";
        if (activeRegInput) activeRegInput.value = path;
        this.updateConfig({ active_regulation_path: path });
      });
    }

    // Quick toggle: Use Vanilla Game Regulation
    const useVanillaRegBtn = document.getElementById("useVanillaRegBtn");
    if (useVanillaRegBtn) {
      useVanillaRegBtn.addEventListener("click", () => {
        const gameDir = document.getElementById("gameDirInput")?.value || "";
        const path = gameDir ? `${gameDir}/regulation.bin` : "regulation.bin";
        if (activeRegInput) activeRegInput.value = path;
        this.updateConfig({ active_regulation_path: path });
      });
    }

    // Scan button
    const scanBtn = document.getElementById("scanModsBtn");
    if (scanBtn) {
      scanBtn.addEventListener("click", () => this.scanMods());
    }

    // Forge button
    const forgeBtn = document.getElementById("forgeAllBtn");
    if (forgeBtn) {
      forgeBtn.addEventListener("click", () => this.forgeMods());
    }

    // Backup button
    const backupBtn = document.getElementById("createBackupBtn");
    if (backupBtn) {
      backupBtn.addEventListener("click", () => this.createBackup());
    }

    // Restore button
    const restoreBtn = document.getElementById("restoreBackupBtn");
    if (restoreBtn) {
      restoreBtn.addEventListener("click", () => this.restoreBackup());
    }

    // Uninstall button
    const uninstallBtn = document.getElementById("uninstallBtn");
    if (uninstallBtn) {
      uninstallBtn.addEventListener("click", () => this.uninstallMods());
    }

    // Drag and Drop
    const dropzone = document.getElementById("dropzone");
    if (dropzone) {
      ["dragenter", "dragover"].forEach(event => {
        dropzone.addEventListener(event, (e) => {
          e.preventDefault();
          dropzone.classList.add("dragover");
        });
      });
      ["dragleave", "drop"].forEach(event => {
        dropzone.addEventListener(event, (e) => {
          e.preventDefault();
          dropzone.classList.remove("dragover");
        });
      });
      dropzone.addEventListener("drop", (e) => {
        // Inform user that dropped files are scanned via input_mods
        this.scanMods();
      });
      dropzone.addEventListener("click", () => this.scanMods());
    }
  }

  async loadLocalization(lang) {
    this.currentLocale = lang;
    try {
      const res = await fetch(`/api/localization?lang=${lang}`);
      if (!res.ok) return;
      this.strings = await res.json();
      this.applyLocalization();
    } catch (err) {
      console.error("Localization loading error:", err);
    }
  }

  applyLocalization() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (this.strings[key]) {
        el.textContent = this.strings[key];
      }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (this.strings[key]) {
        el.placeholder = this.strings[key];
      }
    });
  }

  t(key, fallback = "") {
    return this.strings[key] || fallback || key;
  }

  async loadOptions() {
    try {
      const res = await fetch("/api/options");
      if (!res.ok) return;
      this.options = await res.json();
    } catch (err) {
      console.error("Options loading error:", err);
    }
  }

  async refreshStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const status = await res.json();

      const gameDirInput = document.getElementById("gameDirInput");
      if (gameDirInput && status.config.game_directory) {
        gameDirInput.value = status.config.game_directory;
      }

      const activeRegInput = document.getElementById("activeRegInput");
      if (activeRegInput && status.config.active_regulation_path) {
        activeRegInput.value = status.config.active_regulation_path;
      }

      const backupStatusEl = document.getElementById("backupStatusBadge");
      if (backupStatusEl) {
        if (status.backup_count > 0) {
          backupStatusEl.className = "badge badge-green";
          backupStatusEl.textContent = `${this.t("status_backup_ready")} (${status.backup_count})`;
        } else {
          backupStatusEl.className = "badge badge-gold";
          backupStatusEl.textContent = this.t("status_backup_none");
        }
      }

      const injectedCountEl = document.getElementById("injectedCountLabel");
      if (injectedCountEl) {
        injectedCountEl.textContent = status.injected_count || 0;
      }
    } catch (err) {
      console.error("Status refresh error:", err);
    }
  }

  async updateConfig(payload) {
    try {
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      await this.refreshStatus();
    } catch (err) {
      console.error("Config update error:", err);
    }
  }

  getActiveRegulationPath() {
    return document.getElementById("activeRegInput")?.value?.trim() || "";
  }

  async scanMods() {
    const tableBody = document.getElementById("modTableBody");
    if (!tableBody) return;
    tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--gold-primary); padding: 24px;">Scanning input_mods directory...</td></tr>`;

    try {
      const res = await fetch("/api/scan");
      if (!res.ok) throw new Error("Failed to scan mods");
      const data = await res.json();
      this.scannedSets = data.sets || [];
      this.renderTable(this.scannedSets);
    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--accent-red); padding: 24px;">Error scanning mods: ${err.message}</td></tr>`;
    }
  }

  renderTable(sets) {
    const tableBody = document.getElementById("modTableBody");
    if (!tableBody) return;

    if (!sets || sets.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 32px;">${this.t("err_no_mods_found", "No mods found in input_mods folder. Drop your .partsbnd.dcx files in input_mods to begin.")}</td></tr>`;
      return;
    }

    tableBody.innerHTML = "";
    sets.forEach((set, index) => {
      const tr = document.createElement("tr");

      // Build target options dropdown
      const targetSelectHtml = this.buildTargetSelectHtml(set, index);

      tr.innerHTML = `
        <td>
          <strong>${this.escapeHtml(set.folder_name)}</strong>
          <div style="font-size: 11px; color: var(--text-muted);">${set.parts_count} part file(s)</div>
        </td>
        <td>
          <span style="color: var(--gold-bright); font-weight: 500;">${this.escapeHtml(set.target_vanilla_name)}</span>
          <div style="font-size: 11px; color: var(--text-muted);">Model ID: ${set.target_model_id}</div>
        </td>
        <td>
          <span class="badge badge-blue">Model: ${set.allocated_model_id}</span>
          <div style="font-size: 11px; color: var(--text-secondary); margin-top: 3px;">Param: ${set.allocated_param_id}</div>
        </td>
        <td>
          ${targetSelectHtml}
        </td>
        <td>
          <input type="number" id="cost_input_${index}" class="table-input" value="${set.default_chance_cost || 20}" min="1" max="500000">
        </td>
        <td>
          <span class="badge badge-green">${this.t("badge_ready", "Ready")}</span>
        </td>
        <td style="text-align: center;">
          <input type="checkbox" id="enable_check_${index}" checked style="accent-color: var(--gold-primary); cursor: pointer; transform: scale(1.2);">
        </td>
      `;
      tableBody.appendChild(tr);
    });
  }

  buildTargetSelectHtml(set, index) {
    let optionsHtml = "";

    // Group 1: Boss Remembrances
    optionsHtml += `<optgroup label="Boss Soul Remembrances (Enia Trade)">`;
    this.options.boss_remembrances.forEach((boss) => {
      const selected = (set.default_target_id === boss.id) ? "selected" : "";
      optionsHtml += `<option value="boss_remembrance|${boss.id}|${this.escapeHtml(boss.name)}" ${selected}>${this.escapeHtml(boss.name)}</option>`;
    });
    optionsHtml += `</optgroup>`;

    // Group 2: Elite Enemy Drop Tables
    optionsHtml += `<optgroup label="Enemy Drop Tables">`;
    this.options.elite_enemies.forEach((enemy) => {
      const selected = (set.default_target_id === enemy.id) ? "selected" : "";
      optionsHtml += `<option value="enemy_drop|${enemy.id}|${this.escapeHtml(enemy.name)}" ${selected}>${this.escapeHtml(enemy.name)}</option>`;
    });
    optionsHtml += `</optgroup>`;

    // Group 3: Merchants
    optionsHtml += `<optgroup label="Merchant Shops">`;
    this.options.merchants.forEach((m) => {
      const selected = (set.default_target_id === m.id) ? "selected" : "";
      optionsHtml += `<option value="merchant_shop|${m.id}|${this.escapeHtml(m.name)}" ${selected}>${this.escapeHtml(m.name)}</option>`;
    });
    optionsHtml += `</optgroup>`;

    return `<select id="target_select_${index}" class="table-select">${optionsHtml}</select>`;
  }

  async forgeMods() {
    if (!this.scannedSets || this.scannedSets.length === 0) {
      alert(this.t("err_no_mods_found", "No mods detected to forge."));
      return;
    }

    const payloadSets = [];
    this.scannedSets.forEach((set, index) => {
      const check = document.getElementById(`enable_check_${index}`);
      if (!check || !check.checked) return;

      const targetSelect = document.getElementById(`target_select_${index}`);
      const costInput = document.getElementById(`cost_input_${index}`);

      let routeType = set.default_route;
      let targetId = set.default_target_id;
      let targetName = set.default_display_name;

      if (targetSelect && targetSelect.value) {
        const parts = targetSelect.value.split("|");
        routeType = parts[0];
        targetId = parts[1];
        targetName = parts[2];
      }

      const cost = costInput ? parseFloat(costInput.value) : 20.0;

      payloadSets.push({
        set_id: set.set_id,
        route_type: routeType,
        target_id: targetId,
        target_name: targetName,
        chance_or_cost: cost
      });
    });

    if (payloadSets.length === 0) {
      alert("Please select at least one mod set to forge.");
      return;
    }

    try {
      const activePath = this.getActiveRegulationPath();
      const res = await fetch("/api/forge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: activePath, sets: payloadSets })
      });
      const data = await res.json();
      if (data.success) {
        alert(this.t("msg_forge_success", `Successfully forged ${data.injected_count} standalone item set(s)!`).replace("{count}", data.injected_count));
        await this.refreshStatus();
      } else {
        alert("Forge failed: " + (data.error || "Unknown error"));
      }
    } catch (err) {
      alert("Network error executing forge: " + err.message);
    }
  }

  async createBackup() {
    try {
      const activePath = this.getActiveRegulationPath();
      const res = await fetch("/api/backup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: activePath })
      });
      const data = await res.json();
      if (data.success) {
        alert(this.t("msg_backup_created", `Backup created: ${data.backup}`).replace("{filename}", data.backup));
        await this.refreshStatus();
      } else {
        alert("Backup failed: " + data.error);
      }
    } catch (err) {
      alert("Error creating backup: " + err.message);
    }
  }

  async restoreBackup() {
    if (!confirm("Are you sure you want to restore the latest regulation backup? This will revert parameter injections.")) {
      return;
    }
    try {
      const activePath = this.getActiveRegulationPath();
      const res = await fetch("/api/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: activePath })
      });
      const data = await res.json();
      if (data.success) {
        alert(this.t("msg_restore_success", "Regulation restored successfully."));
        await this.refreshStatus();
      } else {
        alert("Restore failed: " + data.error);
      }
    } catch (err) {
      alert("Error restoring backup: " + err.message);
    }
  }

  async uninstallMods() {
    if (!confirm("Are you sure you want to uninstall and remove all staged standalone assets?")) {
      return;
    }
    try {
      const res = await fetch("/api/uninstall", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      const data = await res.json();
      if (data.success) {
        alert(this.t("msg_uninstall_success", "Injected mods cleanly uninstalled."));
        await this.refreshStatus();
        await this.scanMods();
      } else {
        alert("Uninstall failed: " + data.error);
      }
    } catch (err) {
      alert("Error during uninstall: " + err.message);
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.lootForgeApp = new LootForgeApp();
});
