import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./api.js";

describe("ApiClient", () => {
  it("returns parsed JSON", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ user: { email: "runner@example.com" } }),
    });
    const api = new ApiClient({ fetchImpl });

    await expect(api.getSession()).resolves.toEqual({
      user: { email: "runner@example.com" },
    });
  });

  it("notifies the shell when a session expires", async () => {
    const onUnauthorized = vi.fn();
    const api = new ApiClient({
      onUnauthorized,
      fetchImpl: vi.fn().mockResolvedValue({ ok: false, status: 401 }),
    });

    await expect(api.getMessages()).rejects.toEqual(
      expect.objectContaining({ name: "ApiError", status: 401 }),
    );
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("uses a server error detail when available", async () => {
    const api = new ApiClient({
      fetchImpl: vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "Mailbox is unavailable" }),
      }),
    });

    await expect(api.getMessages()).rejects.toEqual(
      new ApiError("Mailbox is unavailable", 503),
    );
  });
});
