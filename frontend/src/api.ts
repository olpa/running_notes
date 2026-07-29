import type {
  ImapSettingsResponse,
  MessagesResponse,
  NoteMetadata,
  RegeneratedImapPasswordResponse,
  SessionResponse,
} from "./contracts.js";

interface ApiClientOptions {
  fetchImpl?: typeof fetch;
  onUnauthorized?: () => void;
}

interface RequestBehavior {
  notifyUnauthorized?: boolean;
}

interface ApiErrorBody {
  detail?: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ApiClient {
  private readonly fetchImpl: typeof fetch;
  private readonly onUnauthorized: () => void;

  constructor({
    fetchImpl = window.fetch.bind(window),
    onUnauthorized = (): void => {},
  }: ApiClientOptions = {}) {
    this.fetchImpl = fetchImpl;
    this.onUnauthorized = onUnauthorized;
  }

  private async fetchResponse(
    url: string,
    options: RequestInit = {},
    { notifyUnauthorized = true }: RequestBehavior = {},
  ): Promise<Response> {
    const response = await this.fetchImpl(url, options);
    if (response.status === 401) {
      if (notifyUnauthorized) this.onUnauthorized();
      throw new ApiError("Not signed in", 401);
    }
    if (!response.ok) {
      let detail: string | undefined;
      try {
        const body: unknown = await response.json();
        if (isApiErrorBody(body)) detail = body.detail;
      } catch {
        // Non-JSON error responses still receive a useful status message.
      }
      throw new ApiError(detail || `HTTP ${response.status}`, response.status);
    }
    return response;
  }

  private async requestJson<T>(
    url: string,
    options: RequestInit = {},
    behavior: RequestBehavior = {},
  ): Promise<T> {
    const response = await this.fetchResponse(url, options, behavior);
    return response.json() as Promise<T>;
  }

  private async requestEmpty(url: string, options: RequestInit): Promise<void> {
    await this.fetchResponse(url, options);
  }

  getSession(): Promise<SessionResponse> {
    return this.requestJson<SessionResponse>("/api/me", {}, { notifyUnauthorized: false });
  }

  loginAsGuest(): Promise<void> {
    return this.requestEmpty("/auth/guest", { method: "POST" });
  }

  logout(): Promise<void> {
    return this.requestEmpty("/auth/logout", { method: "POST" });
  }

  getMessages(include: string | null = null): Promise<MessagesResponse> {
    const query = include ? `?include=${encodeURIComponent(include)}` : "";
    return this.requestJson<MessagesResponse>(`/api/messages${query}`);
  }

  deleteMessage(messageKey: string): Promise<void> {
    return this.requestEmpty(`/api/messages/${encodeURIComponent(messageKey)}`, {
      method: "DELETE",
    });
  }

  getImapSettings(): Promise<ImapSettingsResponse> {
    return this.requestJson<ImapSettingsResponse>("/api/me/imap-settings");
  }

  regenerateImapPassword(): Promise<RegeneratedImapPasswordResponse> {
    return this.requestJson<RegeneratedImapPasswordResponse>(
      "/api/me/imap-password",
      { method: "POST" },
    );
  }

  uploadRecording(formData: FormData): Promise<NoteMetadata> {
    return this.requestJson<NoteMetadata>("/api/record", { method: "POST", body: formData });
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null) return false;
  if (!("detail" in value)) return true;
  return typeof value.detail === "string";
}
