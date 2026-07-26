import "../styles.css";
import { ApiClient, ApiError } from "./api.js";
import { showStatus } from "./dom.js";
import { createSession } from "./session.js";
import { createTabs } from "./tabs.js";
import "./components/account-tab/account-tab.js";
import "./components/imap-tab/imap-tab.js";
import "./components/messages-tab/messages-tab.js";
import "./components/record-tab/record-tab.js";

const elements = {
  login: document.getElementById("login"),
  portal: document.getElementById("portal"),
  loginStatus: document.getElementById("loginStatus"),
  signedInEmail: document.getElementById("signedInEmail"),
  guestPrivacyWarning: document.getElementById("guestPrivacyWarning"),
  guestRetentionHours: document.getElementById("guestRetentionHours"),
  recorder: document.querySelector("rn-record-tab"),
  messages: document.querySelector("rn-messages-tab"),
  imap: document.querySelector("rn-imap-tab"),
  account: document.querySelector("rn-account-tab"),
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

document.getElementById("googleLogin").addEventListener("click", () => {
  window.location.href = "/auth/login/google";
});
document.getElementById("microsoftLogin").addEventListener("click", () => {
  window.location.href = "/auth/login/microsoft";
});
document.getElementById("guestLogin").addEventListener("click", loginAsGuest);
document.getElementById("topLogout").addEventListener("click", logout);
elements.portal.addEventListener("logout-requested", logout);

function showPortal(user) {
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

function showLoggedOut(message) {
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

async function loginAsGuest() {
  sessionRequestId += 1;
  showStatus(elements.loginStatus, "Opening public guest account...", "busy");
  try {
    await api.loginAsGuest();
    await loadSession();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return;
    loggedOutMessage = `Guest account unavailable: ${error.message}`;
    session.clear();
  }
}

async function logout() {
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

async function loadSession() {
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
      loggedOutMessage = `Session check failed: ${error.message}`;
    }
    session.clear();
  }
}

loadSession();
