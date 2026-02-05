const API_KEY_STORAGE_KEY = "agentbook_api_key";

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(API_KEY_STORAGE_KEY);
}

export function setStoredApiKey(apiKey: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(API_KEY_STORAGE_KEY, apiKey);
}
