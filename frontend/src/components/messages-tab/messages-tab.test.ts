import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../api.js";
import "./messages-tab.js";

describe("rn-messages-tab", () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  it("renders mailbox values as text and delegates audio to playback components", () => {
    const tab = document.createElement("rn-messages-tab");
    document.body.append(tab);

    tab.render([{
      id: "1/2",
      subject: "<strong>not markup</strong>",
      date: "2026-07-26T12:00:00Z",
      from: "sender@example.com",
      preview: "A voice note",
      audio: [{ index: 3, filename: "audio.mp3", content_type: "audio/mpeg" }],
    }]);

    expect(tab.querySelector(".message-subject")?.textContent).toBe("<strong>not markup</strong>");
    expect(tab.querySelector(".message-subject strong")).toBeNull();
    expect(tab.querySelector("rn-playback")?.getAttribute("src")).toBe(
      "/api/messages/1%2F2/audio/3",
    );
    expect(tab.querySelector<HTMLAnchorElement>(".download-audio")?.getAttribute("href")).toBe(
      "/api/messages/1%2F2/audio/3",
    );
    expect(tab.querySelector<HTMLAnchorElement>(".download-audio")?.download).toBe(
      "strong-not markup-strong.mp3",
    );
    expect(tab.querySelector<HTMLAnchorElement>(".download-audio")?.ariaLabel).toBe(
      "Download audio",
    );
    expect(tab.querySelector<HTMLAnchorElement>(".message-subject a")?.pathname).toBe(
      "/messages/1%2F2",
    );
  });

  it("clears rendered mailbox data on reset", () => {
    const tab = document.createElement("rn-messages-tab");
    document.body.append(tab);
    tab.render([{
      id: "1",
      subject: "Note",
      date: null,
      from: "",
      preview: "",
      audio: [],
    }]);

    tab.reset();

    expect(tab.querySelector(".message-list")?.children).toHaveLength(0);
  });

  it("highlights a linked message", () => {
    const tab = document.createElement("rn-messages-tab");
    document.body.append(tab);

    tab.render([{
      id: "selected",
      subject: "Selected note",
      date: null,
      from: "",
      preview: "",
      audio: [{ index: 0 }],
    }], "selected");

    expect(tab.querySelector(".linked-message .linked-message-marker")?.textContent)
      .toBe("Linked message");
  });

  it("confirms, deletes, and reloads a message", async () => {
    const fetchImpl: typeof fetch = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(Response.json({
        messages: [],
        limit: 100,
        requested_message_found: null,
      }));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const tab = document.createElement("rn-messages-tab");
    document.body.append(tab);
    tab.api = new ApiClient({ fetchImpl });
    tab.setUser({
      email: "runner@example.com",
      auth_provider: "google",
      is_guest: false,
      guest_retention_hours: null,
      can_change_imap_password: true,
    });
    tab.render([{
      id: "mailbox/key",
      subject: "Morning run",
      date: null,
      from: "",
      preview: "",
      audio: [],
    }]);

    tab.querySelector<HTMLButtonElement>(".delete-message")?.click();

    await vi.waitFor(() => {
      expect(fetchImpl).toHaveBeenNthCalledWith(
        1,
        "/api/messages/mailbox%2Fkey",
        { method: "DELETE" },
      );
      expect(tab.querySelector(".message")).toBeNull();
    });
    expect(window.confirm).toHaveBeenCalledWith(
      "Permanently delete “Morning run”?",
    );
  });

  it("does not offer message deletion to guest users", () => {
    const tab = document.createElement("rn-messages-tab");
    document.body.append(tab);
    tab.setUser({
      email: "guest@example.com",
      auth_provider: null,
      is_guest: true,
      guest_retention_hours: 24,
      can_change_imap_password: false,
    });

    tab.render([{
      id: "shared-message",
      subject: "Shared voice note",
      date: null,
      from: "",
      preview: "",
      audio: [],
    }]);

    expect(tab.querySelector(".delete-message")).toBeNull();
  });

  it("shows the list and an informational notice when a linked message is unavailable", async () => {
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      Response.json({
        messages: [{
          id: "another",
          subject: "Another note",
          date: null,
          from: "",
          preview: "",
          audio: [],
        }],
        limit: 100,
        requested_message_found: false,
      })
    ));
    const tab = document.createElement("rn-messages-tab");
    document.body.append(tab);
    tab.api = new ApiClient({ fetchImpl });
    tab.setRequestedMessage("missing", true);

    tab.activate();

    await vi.waitFor(() => {
      expect(tab.querySelector(".message-subject")?.textContent).toBe("Another note");
    });
    expect(tab.querySelector<HTMLElement>(".linked-message-notice")?.hidden).toBe(false);
  });
});
