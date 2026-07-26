export interface User {
  email: string;
  is_guest: boolean;
  guest_retention_hours: number | null;
  can_change_imap_password: boolean;
}

export interface SessionResponse {
  user: User;
}

export interface AudioAttachment {
  index: number;
}

export interface MessageSummary {
  id: string;
  subject: string;
  date: string | null;
  from: string;
  preview: string;
  audio: AudioAttachment[];
}

export interface MessagesResponse {
  messages: MessageSummary[];
  limit: number;
}

export interface ImapSettings {
  host: string;
  port: number;
  smtp_port: number;
  security: string;
  username: string;
  password?: string;
}

export interface ImapSettingsResponse {
  imap: ImapSettings;
}

export interface RegeneratedImapPassword {
  username: string;
  password: string;
}

export interface RegeneratedImapPasswordResponse {
  imap: RegeneratedImapPassword;
}

export interface NoteMetadata {
  id: string;
  created_at: string;
  subject: string;
  user_id: number;
}

export type SessionState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: User };

export interface TabComponent extends HTMLElement {
  activate(): void;
  deactivate(): void;
}
