import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../api.js";
import "./record-tab.js";

class FakeMediaStream {
  readonly stop = vi.fn();

  getTracks(): Array<{ stop: () => void }> {
    return [{ stop: this.stop }];
  }
}

class FakeMediaRecorder extends EventTarget {
  static isTypeSupported(): boolean {
    return true;
  }

  state: RecordingState = "inactive";

  start(): void {
    this.state = "recording";
  }

  stop(): void {
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
      expect(tab.querySelector(".record-button")?.textContent).toBe("Stop");
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
});
