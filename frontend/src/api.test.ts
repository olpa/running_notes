import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./api.js";

describe("ApiClient", () => {
  it("returns parsed JSON", async () => {
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      Response.json({
        user: {
          email: "runner@example.com",
          is_guest: false,
          guest_retention_hours: null,
          can_change_imap_password: true,
        },
      })
    ));
    const api = new ApiClient({ fetchImpl });

    await expect(api.getSession()).resolves.toEqual({
      user: {
        email: "runner@example.com",
        is_guest: false,
        guest_retention_hours: null,
        can_change_imap_password: true,
      },
    });
  });

  it("notifies the shell when a session expires", async () => {
    const onUnauthorized = vi.fn();
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      new Response(null, { status: 401 })
    ));
    const api = new ApiClient({
      onUnauthorized,
      fetchImpl,
    });

    await expect(api.getMessages()).rejects.toEqual(
      expect.objectContaining({ name: "ApiError", status: 401 }),
    );
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("uses a server error detail when available", async () => {
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      Response.json({ detail: "Mailbox is unavailable" }, { status: 503 })
    ));
    const api = new ApiClient({
      fetchImpl,
    });

    await expect(api.getMessages()).rejects.toEqual(
      new ApiError("Mailbox is unavailable", 503),
    );
  });

  it("requests inclusion of an opaque linked-message key", async () => {
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      Response.json({
        messages: [],
        limit: 100,
        requested_message_found: false,
      })
    ));
    const api = new ApiClient({ fetchImpl });

    await api.getMessages("mailbox/key");

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/messages?include=mailbox%2Fkey",
      {},
    );
  });

  it("deletes an opaque message key", async () => {
    const fetchImpl: typeof fetch = vi.fn(async (): Promise<Response> => (
      new Response(null, { status: 204 })
    ));
    const api = new ApiClient({ fetchImpl });

    await api.deleteMessage("mailbox/key");

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/messages/mailbox%2Fkey",
      { method: "DELETE" },
    );
  });
});
