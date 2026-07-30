import type { AppRoute, TabName } from "./contracts.js";

const TAB_PATHS: Readonly<Record<TabName, string>> = {
  record: "/record",
  messages: "/messages",
  imap: "/mail-client-settings",
  account: "/account",
};

export function parseRoute(pathname: string): AppRoute {
  if (pathname === "/messages") {
    return { tab: "messages", messageKey: null, messageRequested: false };
  }
  if (pathname.startsWith("/messages/")) {
    const encodedKey = pathname.slice("/messages/".length);
    let messageKey: string | null = null;
    try {
      messageKey = decodeURIComponent(encodedKey);
    } catch {
      // The messages page will display the same unavailable notice as a missing key.
    }
    return { tab: "messages", messageKey, messageRequested: true };
  }

  const tab = (Object.entries(TAB_PATHS) as [TabName, string][])
    .find(([, path]) => path === pathname)?.[0];
  return {
    tab: tab ?? "record",
    messageKey: null,
    messageRequested: false,
  };
}

export function pathForTab(tab: TabName): string {
  return TAB_PATHS[tab];
}

export function pathForMessage(messageKey: string): string {
  return `/messages/${encodeURIComponent(messageKey)}`;
}
