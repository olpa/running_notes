import { describe, expect, it } from "vitest";
import { parseRoute, pathForMessage, pathForTab } from "./router.js";

describe("router", () => {
  it("maps top-level paths to tabs", () => {
    expect(parseRoute("/imap")).toEqual({
      tab: "imap",
      messageKey: null,
      messageRequested: false,
    });
    expect(pathForTab("account")).toBe("/account");
  });

  it("round-trips an opaque message key", () => {
    const key = "mailbox/key";
    const path = pathForMessage(key);

    expect(path).toBe("/messages/mailbox%2Fkey");
    expect(parseRoute(path)).toEqual({
      tab: "messages",
      messageKey: key,
      messageRequested: true,
    });
  });

  it("keeps malformed message routes on the messages page", () => {
    expect(parseRoute("/messages/%E0%A4%A")).toEqual({
      tab: "messages",
      messageKey: null,
      messageRequested: true,
    });
  });
});
