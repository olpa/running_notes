import template from "./imap-tab.html?raw";
import { ApiClient, ApiError } from "../../api.js";
import type { ImapSettings, User } from "../../contracts.js";
import { copyText, errorMessage, queryRequired, showStatus } from "../../dom.js";

export class ImapTab extends HTMLElement {
  private initialized = false;
  private apiClient: ApiClient | null = null;
  private user: User | null = null;
  private currentSettings: ImapSettings | null = null;
  private requestId: symbol | null = null;
  private passwordRequestId: symbol | null = null;
  private rows!: HTMLElement;
  private status!: HTMLElement;
  private passwordControls!: HTMLElement;
  private passwordBox!: HTMLElement;
  private newPassword!: HTMLElement;

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.rows = queryRequired<HTMLElement>(this, ".settings-rows");
    this.status = queryRequired<HTMLElement>(this, ".status");
    this.passwordControls = queryRequired<HTMLElement>(this, ".password-controls");
    this.passwordBox = queryRequired<HTMLElement>(this, ".password-box");
    this.newPassword = queryRequired<HTMLElement>(this, ".new-password");
    queryRequired<HTMLButtonElement>(this, ".regenerate-password").addEventListener("click", () => {
      void this.regenerate();
    });
    queryRequired<HTMLButtonElement>(this, ".copy-password").addEventListener("click", (event: MouseEvent) => {
      const button = event.currentTarget as HTMLButtonElement;
      void copyText(this.newPassword.textContent, this.status, button);
    });
  }

  set api(value: ApiClient) {
    this.apiClient = value;
  }

  setUser(user: User | null): void {
    this.user = user;
    const canChange = Boolean(user?.can_change_imap_password);
    this.passwordControls.classList.toggle("hidden", !canChange);
    queryRequired<HTMLElement>(this, ".password-instruction").textContent = canChange
      ? "Generate a new app password here if you do not have one."
      : "Use the guest password shown with these settings.";
  }

  async load(): Promise<void> {
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
      showStatus(this.status, `IMAP settings unavailable: ${errorMessage(error)}`, "error");
    }
  }

  activate(): void {}
  deactivate(): void {}

  private renderSettings(settings: ImapSettings): void {
    queryRequired<HTMLElement>(this, ".imap-port").textContent = String(settings.port);
    queryRequired<HTMLElement>(this, ".smtp-port").textContent = String(settings.smtp_port);
    const children: HTMLElement[] = [
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

  private createTitle(text: string): HTMLHeadingElement {
    const title = document.createElement("h3");
    title.className = "settings-section-title";
    title.textContent = text;
    return title;
  }

  private createWarning(): HTMLParagraphElement {
    const warning = document.createElement("p");
    warning.className = "settings-warning";
    const strong = document.createElement("strong");
    strong.textContent = "Outgoing delivery is disabled: ";
    warning.append(strong, "SMTP authentication is available for mail-client setup, but every outgoing message is rejected and is not retained or delivered.");
    return warning;
  }

  private createRow(label: string, value: string): HTMLDivElement {
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
    copy.addEventListener("click", () => {
      void copyText(value, this.status, copy);
    });
    row.append(labelElement, valueElement, copy);
    return row;
  }

  private async regenerate(): Promise<void> {
    if (!this.user?.can_change_imap_password) return;
    const apiClient = this.apiClient;
    if (!apiClient) return;
    if (!window.confirm("Regenerate the IMAP password? The old password will stop working immediately.")) return;
    showStatus(this.status, "Regenerating...", "busy");
    this.clearNewPassword();
    const requestId = Symbol();
    this.passwordRequestId = requestId;
    try {
      const data = await apiClient.regenerateImapPassword();
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
      showStatus(this.status, `Regeneration failed: ${errorMessage(error)}`, "error");
    }
  }

  private clearNewPassword(): void {
    this.passwordBox.classList.remove("visible");
    this.newPassword.textContent = "";
  }

  reset(): void {
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
