import "../styles.css";
import { ApiClient, ApiError } from "./api.js";
import { buildInfo, formatBuildInfo } from "./build-info.js";
import type { User } from "./contracts.js";
import { queryRequired, showStatus } from "./dom.js";
import { parseRoute, pathForTab } from "./router.js";
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
  buildInfo: queryRequired<HTMLElement>(document, "#buildInfo"),
};

elements.buildInfo.textContent = formatBuildInfo(buildInfo);

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

const tabs = createTabs(elements.portal, (tab) => navigate(pathForTab(tab)));

session.subscribe(({ status, user }) => {
  if (status === "authenticated") showPortal(user);
  else if (status === "anonymous") showLoggedOut(loggedOutMessage);
});

queryRequired<HTMLButtonElement>(document, "#googleLogin").addEventListener("click", () => {
  startOauthLogin("google");
});
queryRequired<HTMLButtonElement>(document, "#microsoftLogin").addEventListener("click", () => {
  startOauthLogin("microsoft");
});
queryRequired<HTMLButtonElement>(document, "#guestLogin").addEventListener("click", () => {
  void loginAsGuest();
});
queryRequired<HTMLButtonElement>(document, "#topLogout").addEventListener("click", () => {
  void logout();
});
elements.portal.addEventListener("logout-requested", logout);
elements.portal.addEventListener("navigate-requested", (event: Event) => {
  if (event instanceof CustomEvent && typeof event.detail === "string") {
    navigate(event.detail);
  }
});
window.addEventListener("popstate", applyCurrentRoute);

function showPortal(user: User): void {
  elements.login.classList.add("hidden");
  elements.portal.classList.remove("hidden");
  elements.signedInEmail.textContent = user.email;
  elements.guestPrivacyWarning.classList.toggle("hidden", !user.is_guest);
  if (user.is_guest) {
    elements.guestRetentionHours.textContent = String(user.guest_retention_hours);
  }
  elements.recorder.setEnabled(true);
  elements.messages.setUser(user);
  elements.imap.setUser(user);
  elements.account.setUser(user);
  elements.imap.load();
  applyCurrentRoute();
}

function startOauthLogin(provider: "google" | "microsoft"): void {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  window.location.href = `/auth/login/${provider}?return_to=${encodeURIComponent(returnTo)}`;
}

function navigate(path: string): void {
  if (window.location.pathname !== path) {
    window.history.pushState(null, "", path);
  }
  applyCurrentRoute();
}

function applyCurrentRoute(): void {
  const route = parseRoute(window.location.pathname);
  elements.messages.setRequestedMessage(route.messageKey, route.messageRequested);
  if (session.state.status === "authenticated") {
    tabs.select(route.tab);
  }
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
