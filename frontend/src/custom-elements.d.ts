import type { AccountTab } from "./components/account-tab/account-tab.js";
import type { ImapTab } from "./components/imap-tab/imap-tab.js";
import type { MessagesTab } from "./components/messages-tab/messages-tab.js";
import type { PlaybackWidget } from "./components/playback-widget/playback-widget.js";
import type { RecordTab } from "./components/record-tab/record-tab.js";

declare global {
  interface HTMLElementTagNameMap {
    "rn-account-tab": AccountTab;
    "rn-imap-tab": ImapTab;
    "rn-messages-tab": MessagesTab;
    "rn-playback": PlaybackWidget;
    "rn-record-tab": RecordTab;
  }
}

export {};
