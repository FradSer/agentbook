import { UserRole } from "@/lib/types";

const AGENT_API_KEY_STORAGE_KEY = "agentbook_agent_api_key";
const HUMAN_API_KEY_STORAGE_KEY = "agentbook_human_api_key";
const ROLE_STORAGE_KEY = "agentbook_role";

function getItem(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(key);
}

function setItem(key: string, value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(key, value);
}

function removeItem(key: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(key);
}

export function getStoredAgentApiKey(): string | null {
  return getItem(AGENT_API_KEY_STORAGE_KEY);
}

export function setStoredAgentApiKey(apiKey: string): void {
  setItem(AGENT_API_KEY_STORAGE_KEY, apiKey);
}

export function getStoredHumanApiKey(): string | null {
  return getItem(HUMAN_API_KEY_STORAGE_KEY);
}

export function setStoredHumanApiKey(apiKey: string): void {
  setItem(HUMAN_API_KEY_STORAGE_KEY, apiKey);
}

export function clearStoredHumanApiKey(): void {
  removeItem(HUMAN_API_KEY_STORAGE_KEY);
}

export function getStoredRole(): UserRole | null {
  const raw = getItem(ROLE_STORAGE_KEY);
  if (raw === "human" || raw === "agent") {
    return raw;
  }
  return null;
}

export function setStoredRole(role: UserRole): void {
  setItem(ROLE_STORAGE_KEY, role);
}
