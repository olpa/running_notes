export interface BuildInfo {
  commit: string;
  timestamp: string;
}

declare const __BUILD_INFO__: BuildInfo;

export const buildInfo: BuildInfo = __BUILD_INFO__;

export function formatBuildInfo(info: BuildInfo): string {
  const timestamp = new Date(info.timestamp);
  const formattedTimestamp = new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(timestamp);
  return `Built ${formattedTimestamp} UTC · ${info.commit}`;
}
