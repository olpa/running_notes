import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../api.js";
import "./record-tab.js";

class FakeMediaStream {
  readonly stop = vi.fn();

  getTracks(): Array<{ stop: () => void }> {
    return [{ stop: this.stop }];
  }
}

class FakeMediaRecorder extends EventTarget {
  static latest: FakeMediaRecorder | null = null;

  static isTypeSupported(): boolean {
    return true;
  }

  state: RecordingState = "inactive";
  readonly stopCalls = vi.fn();

  constructor() {
    super();
    FakeMediaRecorder.latest = this;
  }

  start(): void {
    this.state = "recording";
  }

  stop(): void {
    this.stopCalls();
    this.state = "inactive";
    this.dispatchEvent(new Event("stop"));
  }
}

describe("rn-record-tab", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    vi.stubGlobal("MediaStream", FakeMediaStream);
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn(async () => new MediaStream()),
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("uploads the first recording after reset and re-enable", async () => {
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      Response.json({
        id: "note-1",
        created_at: "2026-07-26T12:00:00Z",
        subject: "Voice note",
        user_id: "user-1",
      }, { status: 201 })
    ));
    const tab = document.createElement("rn-record-tab");
    document.body.append(tab);
    tab.api = new ApiClient({ fetchImpl });

    tab.reset();
    tab.setEnabled(true);
    tab.querySelector<HTMLButtonElement>(".record-button")?.click();
    await vi.waitFor(() => {
      expect(tab.querySelector(".record-button")?.textContent).toBe("Stop and save");
    });
    tab.querySelector<HTMLButtonElement>(".record-button")?.click();

    await vi.waitFor(() => {
      expect(fetchImpl).toHaveBeenCalledWith(
        "/api/record",
        expect.objectContaining({ method: "POST" }),
      );
      expect(tab.querySelector(".status")?.textContent).toBe("Uploaded");
    });
  });

  it("shows progress and automatically stops at 30 seconds", async () => {
    vi.useFakeTimers();
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      Response.json({
        id: "note-1",
        created_at: "2026-07-26T12:00:00Z",
        subject: "Voice note",
        user_id: "user-1",
      }, { status: 201 })
    ));
    const tab = document.createElement("rn-record-tab");
    document.body.append(tab);
    tab.api = new ApiClient({ fetchImpl });
    tab.setEnabled(true);

    tab.querySelector<HTMLButtonElement>(".record-button")?.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(tab.querySelector(".recording-hint")?.textContent).toContain("30 seconds");
    expect(tab.querySelector<HTMLElement>(".recording-progress")?.hidden).toBe(false);

    vi.advanceTimersByTime(15_000);
    expect(tab.querySelector<HTMLProgressElement>(".recording-progress-bar")?.value).toBe(15);
    expect(tab.querySelector(".recording-time")?.textContent).toBe("0:15 / 0:30");

    vi.advanceTimersByTime(15_000);
    await Promise.resolve();
    await Promise.resolve();

    expect(FakeMediaRecorder.latest?.stopCalls).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/record",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("requires a delayed confirmation before discarding a recording", async () => {
    vi.useFakeTimers();
    const fetchImpl: typeof fetch = vi.fn();
    const tab = document.createElement("rn-record-tab");
    document.body.append(tab);
    tab.api = new ApiClient({ fetchImpl });
    tab.setEnabled(true);

    tab.querySelector<HTMLButtonElement>(".record-button")?.click();
    await Promise.resolve();
    await Promise.resolve();

    const cancel = tab.querySelector<HTMLButtonElement>(".cancel-recording");
    expect(cancel?.hidden).toBe(false);
    expect(tab.querySelector(".record-button")?.textContent).toBe("Stop and save");

    cancel?.click();
    expect(cancel?.textContent).toBe("Discard recording?");
    expect(cancel?.disabled).toBe(true);
    expect(tab.querySelector(".status")?.textContent).toBe(
      "This recording will not be saved.",
    );

    vi.advanceTimersByTime(599);
    expect(cancel?.disabled).toBe(true);
    vi.advanceTimersByTime(1);
    expect(cancel?.disabled).toBe(false);

    cancel?.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(FakeMediaRecorder.latest?.stopCalls).toHaveBeenCalledTimes(1);
    expect(cancel?.hidden).toBe(true);
    expect(tab.querySelector(".record-button")?.textContent).toBe("Record");
    expect(tab.querySelector(".status")?.textContent).toBe(
      "Recording cancelled. Nothing was saved.",
    );
  });

  it("disarms cancellation when the confirmation window expires", async () => {
    vi.useFakeTimers();
    const tab = document.createElement("rn-record-tab");
    document.body.append(tab);
    tab.api = new ApiClient({ fetchImpl: vi.fn() });
    tab.setEnabled(true);

    tab.querySelector<HTMLButtonElement>(".record-button")?.click();
    await Promise.resolve();
    await Promise.resolve();
    const cancel = tab.querySelector<HTMLButtonElement>(".cancel-recording");
    cancel?.click();

    vi.advanceTimersByTime(4_600);

    expect(cancel?.textContent).toBe("Cancel recording");
    expect(cancel?.disabled).toBe(false);
    expect(tab.querySelector(".status")?.textContent).toBe("Recording...");
    expect(FakeMediaRecorder.latest?.stopCalls).not.toHaveBeenCalled();
  });
});
