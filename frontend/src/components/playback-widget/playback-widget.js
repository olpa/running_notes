import template from "./playback-widget.html?raw";

export class PlaybackWidget extends HTMLElement {
  connectedCallback() {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.audio = this.querySelector("audio");
    this.status = this.querySelector(".playback-status");
    this.audio.addEventListener("error", () => {
      this.status.textContent = "Audio unavailable";
      this.status.classList.add("error");
    });
    this.updateSource();
  }

  static get observedAttributes() {
    return ["src"];
  }

  attributeChangedCallback() {
    this.updateSource();
  }

  updateSource() {
    if (!this.audio) return;
    this.status.textContent = "";
    this.status.classList.remove("error");
    this.audio.src = this.getAttribute("src") || "";
  }

  reset() {
    this.audio?.pause();
    if (this.audio) this.audio.currentTime = 0;
  }
}

customElements.define("rn-playback", PlaybackWidget);
