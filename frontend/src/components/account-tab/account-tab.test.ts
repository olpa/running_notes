import { beforeEach, describe, expect, it } from "vitest";
import "./account-tab.js";

describe("rn-account-tab", () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  it("shows the OAuth provider for a signed-in user", () => {
    const tab = document.createElement("rn-account-tab");
    document.body.append(tab);

    tab.setUser({
      email: "runner@example.com",
      auth_provider: "microsoft",
      is_guest: false,
      guest_retention_hours: null,
      can_change_imap_password: true,
    });

    expect(tab.querySelector(".account-email")?.textContent).toBe(
      "runner@example.com via Microsoft",
    );
  });

  it("identifies a guest independently of an OAuth provider", () => {
    const tab = document.createElement("rn-account-tab");
    document.body.append(tab);

    tab.setUser({
      email: "guest@example.com",
      auth_provider: null,
      is_guest: true,
      guest_retention_hours: 24,
      can_change_imap_password: false,
    });

    expect(tab.querySelector(".account-email")?.textContent).toBe(
      "guest@example.com (Guest)",
    );
  });
});
