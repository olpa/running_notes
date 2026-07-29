import template from "./playback-widget.html?raw";
import { queryRequired } from "../../dom.js";

export class PlaybackWidget extends HTMLElement {
  private initialized = false;
  private audio: HTMLAudioElement | null = null;
  private download: HTMLAnchorElement | null = null;
  private status: HTMLElement | null = null;

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.audio = queryRequired<HTMLAudioElement>(this, "audio");
    this.download = queryRequired<HTMLAnchorElement>(this, ".download-audio");
    this.status = queryRequired<HTMLElement>(this, ".playback-status");
    const status = this.status;
    this.audio.addEventListener("error", () => {
      status.textContent = "Audio unavailable";
      status.classList.add("error");
    });
    this.updateSource();
  }

  static get observedAttributes(): string[] {
    return ["src", "filename"];
  }

  attributeChangedCallback(): void {
    this.updateSource();
  }

  private updateSource(): void {
    if (!this.audio || !this.status) return;
    this.status.textContent = "";
    this.status.classList.remove("error");
    const source = this.getAttribute("src") || "";
    this.audio.src = source;
    if (this.download) {
      this.download.href = source;
      this.download.download = this.getAttribute("filename") || "audio";
    }
  }

  reset(): void {
    this.audio?.pause();
    if (this.audio) this.audio.currentTime = 0;
  }
}

customElements.define("rn-playback", PlaybackWidget);
