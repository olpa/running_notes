import template from "./imap-tab.html?raw";
import { ApiError } from "../../api.js";
import { copyText, showStatus } from "../../dom.js";

export class ImapTab extends HTMLElement {
  connectedCallback() {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.rows = this.querySelector(".settings-rows");
    this.status = this.querySelector(".status");
    this.passwordControls = this.querySelector(".password-controls");
    this.passwordBox = this.querySelector(".password-box");
    this.newPassword = this.querySelector(".new-password");
    this.querySelector(".regenerate-password").addEventListener("click", () => this.regenerate());
    this.querySelector(".copy-password").addEventListener("click", (event) => {
      copyText(this.newPassword.textContent, this.status, event.currentTarget);
    });
  }

  set api(value) {
    this.apiClient = value;
  }

  setUser(user) {
    this.user = user;
    const canChange = Boolean(user?.can_change_imap_password);
    this.passwordControls.classList.toggle("hidden", !canChange);
    this.querySelector(".password-instruction").textContent = canChange
      ? "Generate a new app password here if you do not have one."
      : "Use the guest password shown with these settings.";
  }

  async load() {
    if (!this.apiClient || !this.user) return;
    const requestId = Symbol();
    this.requestId = requestId;
    try {
      const data = await this.apiClient.getImapSettings();
      if (this.requestId !== requestId) return;
      this.currentSettings = data.imap;
      this.renderSettings(data.imap);
      showStatus(this.status, "");
    } catch (error) {
      if (this.requestId !== requestId) return;
      if (error instanceof ApiError && error.status === 401) return;
      this.rows.replaceChildren();
      showStatus(this.status, `IMAP settings unavailable: ${error.message}`, "error");
    }
  }

  activate() {}
  deactivate() {}

  renderSettings(settings) {
    this.querySelector(".imap-port").textContent = String(settings.port);
    this.querySelector(".smtp-port").textContent = String(settings.smtp_port);
    const children = [
      this.createRow("Email address", settings.username),
      this.createRow("Username", settings.username),
    ];
    if (settings.password) children.push(this.createRow("Password", settings.password));
    children.push(
      this.createTitle("Incoming"),
      this.createRow("Server type", "IMAP"),
      this.createRow("Server", settings.host),
      this.createRow("Port", String(settings.port)),
      this.createRow("Connection security", "SSL/TLS"),
      this.createRow("Authentication method", "Normal password"),
      this.createWarning(),
      this.createTitle("Outgoing"),
      this.createRow("Server type", "SMTP"),
      this.createRow("Server", settings.host),
      this.createRow("Port", String(settings.smtp_port)),
      this.createRow("Connection security", "STARTTLS"),
      this.createRow("Authentication method", "Normal password"),
    );
    this.rows.replaceChildren(...children);
  }

  createTitle(text) {
    const title = document.createElement("h3");
    title.className = "settings-section-title";
    title.textContent = text;
    return title;
  }

  createWarning() {
    const warning = document.createElement("p");
    warning.className = "settings-warning";
    const strong = document.createElement("strong");
    strong.textContent = "Outgoing delivery is disabled: ";
    warning.append(strong, "SMTP authentication is available for mail-client setup, but every outgoing message is rejected and is not retained or delivered.");
    return warning;
  }

  createRow(label, value) {
    const row = document.createElement("div");
    row.className = "setting-row";
    const labelElement = document.createElement("div");
    labelElement.className = "label";
    labelElement.textContent = label;
    const valueElement = document.createElement("div");
    valueElement.className = "value";
    valueElement.textContent = value;
    const copy = document.createElement("button");
    copy.className = "secondary";
    copy.type = "button";
    copy.textContent = "Copy";
    copy.addEventListener("click", () => copyText(value, this.status, copy));
    row.append(labelElement, valueElement, copy);
    return row;
  }

  async regenerate() {
    if (!this.user?.can_change_imap_password) return;
    if (!window.confirm("Regenerate the IMAP password? The old password will stop working immediately.")) return;
    showStatus(this.status, "Regenerating...", "busy");
    this.clearNewPassword();
    const requestId = Symbol();
    this.passwordRequestId = requestId;
    try {
      const data = await this.apiClient.regenerateImapPassword();
      if (this.passwordRequestId !== requestId) return;
      this.newPassword.textContent = data.imap.password;
      this.passwordBox.classList.add("visible");
      if (this.currentSettings) {
        this.currentSettings = { ...this.currentSettings, username: data.imap.username };
        this.renderSettings(this.currentSettings);
      }
      showStatus(this.status, "Password regenerated. Copy it now; it will not be shown again.", "success");
    } catch (error) {
      if (this.passwordRequestId !== requestId) return;
      if (error instanceof ApiError && error.status === 401) return;
      showStatus(this.status, `Regeneration failed: ${error.message}`, "error");
    }
  }

  clearNewPassword() {
    this.passwordBox.classList.remove("visible");
    this.newPassword.textContent = "";
  }

  reset() {
    this.requestId = null;
    this.passwordRequestId = null;
    this.user = null;
    this.currentSettings = null;
    this.rows.replaceChildren();
    this.clearNewPassword();
    showStatus(this.status, "");
  }
}

customElements.define("rn-imap-tab", ImapTab);
