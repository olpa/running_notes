export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ApiClient {
  constructor({ fetchImpl = window.fetch.bind(window), onUnauthorized = () => {} } = {}) {
    this.fetchImpl = fetchImpl;
    this.onUnauthorized = onUnauthorized;
  }

  async request(url, options = {}, { notifyUnauthorized = true } = {}) {
    const response = await this.fetchImpl(url, options);
    if (response.status === 401) {
      if (notifyUnauthorized) this.onUnauthorized();
      throw new ApiError("Not signed in", 401);
    }
    if (!response.ok) {
      let detail = "";
      try {
        detail = (await response.json()).detail;
      } catch {
        // Non-JSON error responses still receive a useful status message.
      }
      throw new ApiError(detail || `HTTP ${response.status}`, response.status);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  getSession() {
    return this.request("/me", {}, { notifyUnauthorized: false });
  }

  loginAsGuest() {
    return this.request("/auth/guest", { method: "POST" });
  }

  logout() {
    return this.request("/auth/logout", { method: "POST" });
  }

  getMessages() {
    return this.request("/messages");
  }

  getImapSettings() {
    return this.request("/me/imap-settings");
  }

  regenerateImapPassword() {
    return this.request("/me/imap-password", { method: "POST" });
  }

  uploadRecording(formData) {
    return this.request("/record", { method: "POST", body: formData });
  }
}
