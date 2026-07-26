import template from "./messages-tab.html?raw";
import { ApiClient, ApiError } from "../../api.js";
import type { MessageSummary } from "../../contracts.js";
import { errorMessage, queryRequired, showStatus } from "../../dom.js";
import "../playback-widget/playback-widget.js";
import type { PlaybackWidget } from "../playback-widget/playback-widget.js";

export class MessagesTab extends HTMLElement {
  private initialized = false;
  private apiClient: ApiClient | null = null;
  private list!: HTMLElement;
  private status!: HTMLElement;
  private requestId: symbol | null = null;

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.list = queryRequired<HTMLElement>(this, ".message-list");
    this.status = queryRequired<HTMLElement>(this, ".status");
    queryRequired<HTMLButtonElement>(this, ".reload-messages").addEventListener("click", () => {
      void this.load();
    });
  }

  set api(value: ApiClient) {
    this.apiClient = value;
  }

  activate(): void {
    void this.load();
  }

  deactivate(): void {
    // Playback intentionally continues when navigating between tabs.
  }

  async load(): Promise<void> {
    if (!this.apiClient) return;
    const requestId = Symbol();
    this.requestId = requestId;
    showStatus(this.status, "Loading...", "busy");
    try {
      const data = await this.apiClient.getMessages();
      if (this.requestId !== requestId) return;
      this.render(data.messages);
      showStatus(this.status, data.messages.length ? "" : "No messages");
    } catch (error) {
      if (this.requestId !== requestId || error instanceof ApiError && error.status === 401) return;
      showStatus(this.status, `Messages unavailable: ${errorMessage(error)}`, "error");
    }
  }

  render(messages: readonly MessageSummary[]): void {
    this.list.replaceChildren(...messages.map((message) => {
      const article = document.createElement("article");
      article.className = "message";
      const header = document.createElement("div");
      header.className = "message-header";
      const subject = document.createElement("div");
      subject.className = "message-subject";
      subject.textContent = message.subject;
      const date = document.createElement("time");
      date.className = "muted";
      date.textContent = message.date ? new Date(message.date).toLocaleString() : "";
      const from = document.createElement("div");
      from.className = "message-meta";
      from.textContent = message.from;
      const preview = document.createElement("div");
      preview.className = "message-preview";
      preview.textContent = message.preview;
      header.append(subject, date);
      article.append(header, from, preview);
      message.audio.forEach((attachment) => {
        const playback = document.createElement("rn-playback");
        playback.setAttribute("src", `/messages/${encodeURIComponent(message.id)}/audio/${attachment.index}`);
        article.append(playback);
      });
      return article;
    }));
  }

  reset(): void {
    this.requestId = null;
    this.querySelectorAll<PlaybackWidget>("rn-playback").forEach((playback) => playback.reset());
    this.list.replaceChildren();
    showStatus(this.status, "");
  }
}

customElements.define("rn-messages-tab", MessagesTab);
