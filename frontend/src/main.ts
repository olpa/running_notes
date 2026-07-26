import "../styles.css";
import { ApiClient, ApiError } from "./api.js";
import type { User } from "./contracts.js";
import { queryRequired, showStatus } from "./dom.js";
import { createSession } from "./session.js";
import { createTabs } from "./tabs.js";
import { AccountTab } from "./components/account-tab/account-tab.js";
import { ImapTab } from "./components/imap-tab/imap-tab.js";
import { MessagesTab } from "./components/messages-tab/messages-tab.js";
import { RecordTab } from "./components/record-tab/record-tab.js";

const elements = {
  login: queryRequired<HTMLElement>(document, "#login"),
  portal: queryRequired<HTMLElement>(document, "#portal"),
  loginStatus: queryRequired<HTMLElement>(document, "#loginStatus"),
  signedInEmail: queryRequired<HTMLElement>(document, "#signedInEmail"),
  guestPrivacyWarning: queryRequired<HTMLElement>(document, "#guestPrivacyWarning"),
  guestRetentionHours: queryRequired<HTMLElement>(document, "#guestRetentionHours"),
  recorder: queryRequired<RecordTab>(document, "rn-record-tab"),
  messages: queryRequired<MessagesTab>(document, "rn-messages-tab"),
  imap: queryRequired<ImapTab>(document, "rn-imap-tab"),
  account: queryRequired<AccountTab>(document, "rn-account-tab"),
};

const session = createSession();
let loggedOutMessage = "Sign in to continue";
let sessionRequestId = 0;
const api = new ApiClient({
  onUnauthorized: () => {
    sessionRequestId += 1;
    loggedOutMessage = "Session expired. Sign in again.";
    session.clear();
  },
});

[elements.recorder, elements.messages, elements.imap].forEach((component) => {
  component.api = api;
});

const tabs = createTabs(elements.portal);
tabs.select("record");

session.subscribe(({ status, user }) => {
  if (status === "authenticated") showPortal(user);
  else if (status === "anonymous") showLoggedOut(loggedOutMessage);
});

queryRequired<HTMLButtonElement>(document, "#googleLogin").addEventListener("click", () => {
  window.location.href = "/auth/login/google";
});
queryRequired<HTMLButtonElement>(document, "#microsoftLogin").addEventListener("click", () => {
  window.location.href = "/auth/login/microsoft";
});
queryRequired<HTMLButtonElement>(document, "#guestLogin").addEventListener("click", () => {
  void loginAsGuest();
});
queryRequired<HTMLButtonElement>(document, "#topLogout").addEventListener("click", () => {
  void logout();
});
elements.portal.addEventListener("logout-requested", logout);

function showPortal(user: User): void {
  elements.login.classList.add("hidden");
  elements.portal.classList.remove("hidden");
  elements.signedInEmail.textContent = user.email;
  elements.guestPrivacyWarning.classList.toggle("hidden", !user.is_guest);
  if (user.is_guest) {
    elements.guestRetentionHours.textContent = String(user.guest_retention_hours);
  }
  elements.recorder.setEnabled(true);
  elements.imap.setUser(user);
  elements.account.setUser(user);
  elements.imap.load();
}

function showLoggedOut(message: string): void {
  elements.portal.classList.add("hidden");
  elements.login.classList.remove("hidden");
  elements.signedInEmail.textContent = "";
  elements.guestPrivacyWarning.classList.add("hidden");
  elements.recorder.reset();
  elements.messages.reset();
  elements.imap.reset();
  elements.account.reset();
  showStatus(elements.loginStatus, message);
}

async function loginAsGuest(): Promise<void> {
  sessionRequestId += 1;
  showStatus(elements.loginStatus, "Opening public guest account...", "busy");
  try {
    await api.loginAsGuest();
    await loadSession();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return;
    loggedOutMessage = `Guest account unavailable: ${error instanceof Error ? error.message : String(error)}`;
    session.clear();
  }
}

async function logout(): Promise<void> {
  sessionRequestId += 1;
  try {
    await api.logout();
  } catch {
    // The local session is still cleared when the server is unavailable.
  } finally {
    loggedOutMessage = "Signed out";
    session.clear();
  }
}

async function loadSession(): Promise<void> {
  const requestId = ++sessionRequestId;
  try {
    const data = await api.getSession();
    if (requestId !== sessionRequestId) return;
    loggedOutMessage = "Sign in to continue";
    session.authenticate(data.user);
  } catch (error) {
    if (requestId !== sessionRequestId) return;
    if (error instanceof ApiError && error.status === 401) {
      loggedOutMessage = "Sign in to continue";
    } else {
      loggedOutMessage = `Session check failed: ${error instanceof Error ? error.message : String(error)}`;
    }
    session.clear();
  }
}

void loadSession();
