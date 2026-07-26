import type { SessionState, User } from "./contracts.js";

export interface Session {
  readonly state: SessionState;
  authenticate(user: User): void;
  clear(): void;
  subscribe(listener: SessionListener): () => void;
}

type SessionListener = (state: SessionState) => void;

export function createSession(): Session {
  let state: SessionState = { status: "loading", user: null };
  const listeners = new Set<SessionListener>();

  return {
    get state() {
      return state;
    },
    authenticate(user: User): void {
      state = { status: "authenticated", user };
      listeners.forEach((listener) => listener(state));
    },
    clear(): void {
      state = { status: "anonymous", user: null };
      listeners.forEach((listener) => listener(state));
    },
    subscribe(listener: SessionListener): () => void {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
