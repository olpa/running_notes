import template from "./messages-tab.html?raw";
import { ApiClient, ApiError } from "../../api.js";
import type { MessageSummary } from "../../contracts.js";
import { errorMessage, queryRequired, showStatus } from "../../dom.js";
import { pathForMessage } from "../../router.js";
import "../playback-widget/playback-widget.js";
import type { PlaybackWidget } from "../playback-widget/playback-widget.js";

export class MessagesTab extends HTMLElement {
  private initialized = false;
  private apiClient: ApiClient | null = null;
  private list!: HTMLElement;
  private status!: HTMLElement;
  private notice!: HTMLElement;
  private requestId: symbol | null = null;
  private requestedMessageKey: string | null = null;
  private messageRequested = false;

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.list = queryRequired<HTMLElement>(this, ".message-list");
    this.status = queryRequired<HTMLElement>(this, ".status");
    this.notice = queryRequired<HTMLElement>(this, ".linked-message-notice");
    queryRequired<HTMLButtonElement>(this, ".reload-messages").addEventListener("click", () => {
      void this.load();
    });
  }

  set api(value: ApiClient) {
    this.apiClient = value;
  }

  setRequestedMessage(messageKey: string | null, requested: boolean): void {
    this.requestedMessageKey = messageKey;
    this.messageRequested = requested;
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
      const data = await this.apiClient.getMessages(this.requestedMessageKey);
      if (this.requestId !== requestId) return;
      const requestedMessageFound = this.messageRequested
        && data.requested_message_found === true;
      this.render(data.messages, requestedMessageFound ? this.requestedMessageKey : null);
      this.notice.hidden = !this.messageRequested || requestedMessageFound;
      showStatus(this.status, data.messages.length ? "" : "No messages");
      if (requestedMessageFound) this.revealRequestedMessage();
    } catch (error) {
      if (this.requestId !== requestId || error instanceof ApiError && error.status === 401) return;
      showStatus(this.status, `Messages unavailable: ${errorMessage(error)}`, "error");
    }
  }

  render(
    messages: readonly MessageSummary[],
    selectedMessageKey: string | null = null,
  ): void {
    this.list.replaceChildren(...messages.map((message) => {
      const article = document.createElement("article");
      article.className = "message";
      const header = document.createElement("div");
      header.className = "message-header";
      const subject = document.createElement("div");
      subject.className = "message-subject";
      const subjectLink = document.createElement("a");
      subjectLink.href = pathForMessage(message.id);
      subjectLink.textContent = message.subject;
      subjectLink.addEventListener("click", (event: MouseEvent) => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        event.preventDefault();
        this.dispatchEvent(new CustomEvent<string>("navigate-requested", {
          bubbles: true,
          detail: subjectLink.pathname,
        }));
      });
      subject.append(subjectLink);
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
      article.dataset.messageId = message.id;
      if (message.id === selectedMessageKey) {
        const marker = document.createElement("div");
        marker.className = "linked-message-marker";
        marker.textContent = "Linked message";
        article.classList.add("linked-message");
        article.tabIndex = -1;
        article.prepend(marker);
      }
      message.audio.forEach((attachment) => {
        const playback = document.createElement("rn-playback");
        playback.setAttribute("src", `/api/messages/${encodeURIComponent(message.id)}/audio/${attachment.index}`);
        playback.setAttribute("filename", attachment.filename || `audio-${attachment.index + 1}`);
        article.append(playback);
      });
      return article;
    }));
  }

  private revealRequestedMessage(): void {
    const selected = [...this.list.children]
      .find((element) => (element as HTMLElement).classList.contains("linked-message"));
    if (!(selected instanceof HTMLElement)) return;
    selected.focus({ preventScroll: true });
    selected.scrollIntoView?.({ behavior: "smooth", block: "center" });
  }

  reset(): void {
    this.requestId = null;
    this.querySelectorAll<PlaybackWidget>("rn-playback").forEach((playback) => playback.reset());
    this.list.replaceChildren();
    this.notice.hidden = true;
    showStatus(this.status, "");
  }
}

customElements.define("rn-messages-tab", MessagesTab);
