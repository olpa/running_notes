import { describe, expect, it, vi } from "vitest";
import { createSession } from "./session.js";

describe("session", () => {
  it("publishes authenticated and anonymous transitions", () => {
    const session = createSession();
    const listener = vi.fn();
    session.subscribe(listener);

    session.authenticate({ email: "runner@example.com" });
    session.clear();

    expect(listener).toHaveBeenNthCalledWith(1, {
      status: "authenticated",
      user: { email: "runner@example.com" },
    });
    expect(listener).toHaveBeenNthCalledWith(2, {
      status: "anonymous",
      user: null,
    });
  });
});
