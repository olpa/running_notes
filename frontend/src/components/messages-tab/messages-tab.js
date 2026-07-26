import template from "./messages-tab.html?raw";
import { ApiError } from "../../api.js";
import { showStatus } from "../../dom.js";
import "../playback-widget/playback-widget.js";

export class MessagesTab extends HTMLElement {
  connectedCallback() {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.list = this.querySelector(".message-list");
    this.status = this.querySelector(".status");
    this.querySelector(".reload-messages").addEventListener("click", () => this.load());
  }

  set api(value) {
    this.apiClient = value;
  }

  activate() {
    this.load();
  }

  deactivate() {
    // Playback intentionally continues when navigating between tabs.
  }

  async load() {
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
      showStatus(this.status, `Messages unavailable: ${error.message}`, "error");
    }
  }

  render(messages) {
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

  reset() {
    this.requestId = null;
    this.querySelectorAll("rn-playback").forEach((playback) => playback.reset());
    this.list.replaceChildren();
    showStatus(this.status, "");
  }
}

customElements.define("rn-messages-tab", MessagesTab);
