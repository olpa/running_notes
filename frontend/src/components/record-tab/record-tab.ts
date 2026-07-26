import template from "./record-tab.html?raw";
import { ApiClient, ApiError } from "../../api.js";
import { errorMessage, queryRequired, showStatus } from "../../dom.js";

type RecorderState = "disabled" | "idle" | "requesting" | "recording" | "uploading";

export class RecordTab extends HTMLElement {
  private initialized = false;
  private apiClient: ApiClient | null = null;
  private button!: HTMLButtonElement;
  private status!: HTMLElement;
  private enabled = false;
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private mimeType = "audio/webm";
  private discardOnStop = false;
  private recorderState: RecorderState = "disabled";

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.button = queryRequired<HTMLButtonElement>(this, ".record-button");
    this.status = queryRequired<HTMLElement>(this, ".status");
    this.button.addEventListener("click", () => {
      void this.toggleRecording();
    });
    this.setState("disabled");
  }

  set api(value: ApiClient) {
    this.apiClient = value;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) this.reset();
    else if (this.recorderState === "disabled") this.setState("idle");
  }

  activate(): void {}

  deactivate(): void {
    // Match the previous behavior: switching tabs does not end a recording.
  }

  private setState(state: RecorderState, message?: string): void {
    this.recorderState = state;
    const recording = state === "recording";
    this.button.textContent = recording ? "Stop" : "Record";
    this.button.classList.toggle("recording", recording);
    this.button.disabled = state === "disabled" || state === "requesting" || state === "uploading";
    const defaults: Record<RecorderState, string> = {
      disabled: "Ready",
      idle: "Ready",
      requesting: "Requesting microphone...",
      recording: "Recording...",
      uploading: "Uploading...",
    };
    const statusKind: "" | "busy" =
      state === "recording" || state === "requesting" || state === "uploading"
        ? "busy"
        : "";
    showStatus(this.status, message ?? defaults[state] ?? "", statusKind);
  }

  private async toggleRecording(): Promise<void> {
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
      this.recorder.addEventListener("stop", () => {
        void this.handleStop();
      }, { once: true });
      this.recorder.start();
      this.setState("recording");
    } catch (error) {
      this.stopTracks();
      this.setState("idle");
      showStatus(this.status, `Microphone error: ${errorMessage(error)}`, "error");
    }
  }

  private async handleStop(): Promise<void> {
    this.stopTracks();
    if (this.discardOnStop || !this.enabled) {
      this.discardOnStop = false;
      this.chunks = [];
      this.setState(this.enabled ? "idle" : "disabled");
      return;
    }

    this.setState("uploading");
    const apiClient = this.apiClient;
    if (!apiClient) {
      this.setState(this.enabled ? "idle" : "disabled");
      return;
    }
    const form = new FormData();
    form.append("file", new Blob(this.chunks, { type: this.mimeType }), "audio.webm");
    this.chunks = [];
    try {
      await apiClient.uploadRecording(form);
      if (this.enabled) {
        this.setState("idle");
        showStatus(this.status, "Uploaded", "success");
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return;
      if (this.enabled) {
        this.setState("idle");
        showStatus(this.status, `Upload failed: ${errorMessage(error)}`, "error");
      }
    }
  }

  private stopTracks(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  reset(): void {
    this.enabled = false;
    this.discardOnStop = true;
    if (this.recorder?.state === "recording") this.recorder.stop();
    else this.stopTracks();
    this.chunks = [];
    this.setState("disabled");
  }
}

customElements.define("rn-record-tab", RecordTab);
