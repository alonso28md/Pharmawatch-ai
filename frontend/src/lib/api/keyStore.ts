/**
 * API key storage: in memory by default; optionally mirrored to sessionStorage (cleared
 * when the tab closes). Never written to localStorage.
 */
const SESSION_KEY = "pharmawatch.apiKey";

let memoryKey: string | null = null;
const listeners = new Set<() => void>();

function readSession(): string | null {
  try {
    return window.sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function getApiKey(): string | null {
  return memoryKey ?? readSession();
}

export function isKeyInSession(): boolean {
  return readSession() !== null;
}

export function setApiKey(key: string | null, options: { rememberForSession?: boolean } = {}): void {
  memoryKey = key && key.trim() ? key.trim() : null;
  try {
    if (memoryKey && options.rememberForSession) {
      window.sessionStorage.setItem(SESSION_KEY, memoryKey);
    } else {
      window.sessionStorage.removeItem(SESSION_KEY);
    }
  } catch {
    /* storage unavailable: memory only */
  }
  listeners.forEach((listener) => listener());
}

export function subscribeApiKey(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
