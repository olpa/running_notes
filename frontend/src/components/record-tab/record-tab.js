import template from "./record-tab.html?raw";
import { ApiError } from "../../api.js";
import { showStatus } from "../../dom.js";

export class RecordTab extends HTMLElement {
  connectedCallback() {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.button = this.querySelector(".record-button");
    this.status = this.querySelector(".status");
    this.button.addEventListener("click", () => this.toggleRecording());
    this.setState("disabled");
  }

  set api(value) {
    this.apiClient = value;
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (!enabled) this.reset();
    else if (this.state === "disabled") this.setState("idle");
  }

  activate() {}

  deactivate() {
    // Match the previous behavior: switching tabs does not end a recording.
  }

  setState(state, message) {
    this.state = state;
    const recording = state === "recording";
    this.button.textContent = recording ? "Stop" : "Record";
    this.button.classList.toggle("recording", recording);
    this.button.disabled = state === "disabled" || state === "requesting" || state === "uploading";
    const defaults = {
      disabled: "Ready",
      idle: "Ready",
      requesting: "Requesting microphone...",
      recording: "Recording...",
      uploading: "Uploading...",
    };
    const statusKind = state === "recording" || state === "requesting" || state === "uploading" ? "busy" : "";
    showStatus(this.status, message ?? defaults[state] ?? "", statusKind);
  }

  async toggleRecording() {
    if (!this.enabled || !this.apiClient) return;
    if (this.recorder?.state === "recording") {
      this.recorder.stop();
      return;
    }

    this.setState("requesting");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!this.enabled) {
        this.stopTracks();
        return;
      }
      this.chunks = [];
      this.mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      this.recorder = new MediaRecorder(this.stream, { mimeType: this.mimeType });
      this.recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) this.chunks.push(event.data);
      });
      this.recorder.addEventListener("stop", () => this.handleStop(), { once: true });
      this.recorder.start();
      this.setState("recording");
    } catch (error) {
      this.stopTracks();
      this.setState("idle");
      showStatus(this.status, `Microphone error: ${error.message}`, "error");
    }
  }

  async handleStop() {
    this.stopTracks();
    if (this.discardOnStop || !this.enabled) {
      this.discardOnStop = false;
      this.chunks = [];
      this.setState(this.enabled ? "idle" : "disabled");
      return;
    }

    this.setState("uploading");
    const form = new FormData();
    form.append("file", new Blob(this.chunks, { type: this.mimeType }), "audio.webm");
    this.chunks = [];
    try {
      await this.apiClient.uploadRecording(form);
      if (this.enabled) {
        this.setState("idle");
        showStatus(this.status, "Uploaded", "success");
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return;
      if (this.enabled) {
        this.setState("idle");
        showStatus(this.status, `Upload failed: ${error.message}`, "error");
      }
    }
  }

  stopTracks() {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  reset() {
    this.enabled = false;
    this.discardOnStop = true;
    if (this.recorder?.state === "recording") this.recorder.stop();
    else this.stopTracks();
    this.chunks = [];
    this.setState("disabled");
  }
}

customElements.define("rn-record-tab", RecordTab);
