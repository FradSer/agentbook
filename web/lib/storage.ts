import { UserRole } from "@/lib/types";

const AGENT_API_KEY_STORAGE_KEY = "agentbook_agent_api_key";
const HUMAN_API_KEY_STORAGE_KEY = "agentbook_human_api_key";
const ROLE_STORAGE_KEY = "agentbook_role";
export const ROLE_CHANGED_EVENT = "agentbook-role-change";

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

export function getStoredRole(): UserRole | null {
  const raw = getItem(ROLE_STORAGE_KEY);
  if (raw === "human" || raw === "agent") {
    return raw;
  }
  return null;
}

export function setStoredRole(role: UserRole): void {
  setItem(ROLE_STORAGE_KEY, role);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(ROLE_CHANGED_EVENT));
  }
}
