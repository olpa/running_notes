import template from "./record-tab.html?raw";
import { ApiClient, ApiError } from "../../api.js";
import { errorMessage, queryRequired, showStatus } from "../../dom.js";

type RecorderState = "disabled" | "idle" | "requesting" | "recording" | "uploading";

const MAX_RECORDING_SECONDS = 30;
const RECORDING_PROGRESS_INTERVAL_MS = 100;

export class RecordTab extends HTMLElement {
  private initialized = false;
  private apiClient: ApiClient | null = null;
  private button!: HTMLButtonElement;
  private status!: HTMLElement;
  private progressContainer!: HTMLElement;
  private progressBar!: HTMLProgressElement;
  private recordingTime!: HTMLElement;
  private enabled = false;
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private lifecycleGeneration = 0;
  private recorderState: RecorderState = "disabled";
  private recordingStartedAt = 0;
  private progressInterval: number | null = null;

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.button = queryRequired<HTMLButtonElement>(this, ".record-button");
    this.status = queryRequired<HTMLElement>(this, ".status");
    this.progressContainer = queryRequired<HTMLElement>(this, ".recording-progress");
    this.progressBar = queryRequired<HTMLProgressElement>(this, ".recording-progress-bar");
    this.recordingTime = queryRequired<HTMLElement>(this, ".recording-time");
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
    this.progressContainer.hidden = !recording;
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
      this.stopRecording();
      return;
    }

    const recordingGeneration = this.lifecycleGeneration;
    let requestedStream: MediaStream | null = null;
    this.setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      requestedStream = stream;
      if (!this.enabled || recordingGeneration !== this.lifecycleGeneration) {
        this.stopStream(stream);
        return;
      }
      const chunks: Blob[] = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      this.stream = stream;
      this.recorder = recorder;
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        void this.handleStop({
          chunks,
          generation: recordingGeneration,
          mimeType,
          recorder,
          stream,
        });
      }, { once: true });
      recorder.start();
      this.startRecordingProgress();
      this.setState("recording");
    } catch (error) {
      if (requestedStream) this.stopStream(requestedStream);
      if (recordingGeneration !== this.lifecycleGeneration) return;
      this.setState("idle");
      showStatus(this.status, `Microphone error: ${errorMessage(error)}`, "error");
    }
  }

  private async handleStop(recording: CompletedRecording): Promise<void> {
    this.stopRecordingProgress();
    this.stopStream(recording.stream);
    if (this.stream === recording.stream) this.stream = null;
    if (this.recorder === recording.recorder) this.recorder = null;
    if (!this.enabled || recording.generation !== this.lifecycleGeneration) {
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
    form.append(
      "file",
      new Blob(recording.chunks, { type: recording.mimeType }),
      "audio.webm",
    );
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
    if (this.stream) this.stopStream(this.stream);
    this.stream = null;
  }

  private startRecordingProgress(): void {
    this.recordingStartedAt = Date.now();
    this.updateRecordingProgress(0);
    this.progressInterval = window.setInterval(() => {
      const elapsedSeconds = (Date.now() - this.recordingStartedAt) / 1000;
      this.updateRecordingProgress(elapsedSeconds);
      if (elapsedSeconds >= MAX_RECORDING_SECONDS) this.stopRecording();
    }, RECORDING_PROGRESS_INTERVAL_MS);
  }

  private stopRecording(): void {
    if (this.recorder?.state !== "recording") return;
    this.stopRecordingProgress();
    this.recorder.stop();
  }

  private stopRecordingProgress(): void {
    if (this.progressInterval !== null) {
      window.clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
  }

  private updateRecordingProgress(elapsedSeconds: number): void {
    const boundedSeconds = Math.min(elapsedSeconds, MAX_RECORDING_SECONDS);
    const wholeSeconds = Math.floor(boundedSeconds);
    this.progressBar.value = boundedSeconds;
    this.progressBar.textContent = `${wholeSeconds} of ${MAX_RECORDING_SECONDS} seconds`;
    this.recordingTime.textContent =
      `0:${wholeSeconds.toString().padStart(2, "0")} / 0:30`;
  }

  private stopStream(stream: MediaStream): void {
    stream.getTracks().forEach((track) => track.stop());
  }

  reset(): void {
    this.lifecycleGeneration += 1;
    this.enabled = false;
    if (this.recorder?.state === "recording") this.stopRecording();
    else this.stopTracks();
    this.setState("disabled");
  }
}

interface CompletedRecording {
  chunks: Blob[];
  generation: number;
  mimeType: string;
  recorder: MediaRecorder;
  stream: MediaStream;
}

customElements.define("rn-record-tab", RecordTab);
