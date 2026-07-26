export function createSession() {
  let state = { status: "loading", user: null };
  const listeners = new Set();

  return {
    get state() {
      return state;
    },
    authenticate(user) {
      state = { status: "authenticated", user };
      listeners.forEach((listener) => listener(state));
    },
    clear() {
      state = { status: "anonymous", user: null };
      listeners.forEach((listener) => listener(state));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
