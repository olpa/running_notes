import { beforeEach, describe, expect, it } from "vitest";
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
      audio: [{ index: 3 }],
    }]);

    expect(tab.querySelector(".message-subject")?.textContent).toBe("<strong>not markup</strong>");
    expect(tab.querySelector(".message-subject strong")).toBeNull();
    expect(tab.querySelector("rn-playback")?.getAttribute("src")).toBe(
      "/messages/1%2F2/audio/3",
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
});
