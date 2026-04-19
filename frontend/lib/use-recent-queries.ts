const STORAGE_KEY = "agentbook:recent-queries";
const MAX_RECENT = 5;

function readStorage(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as string[]) : [];
  } catch {
    return [];
  }
}

function writeStorage(items: string[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // storage quota or private mode — silently ignore
  }
}

export function getRecent(): string[] {
  return readStorage();
}

export function pushRecent(q: string): void {
  const trimmed = q.trim();
  if (!trimmed) return;
  const current = readStorage().filter((item) => item !== trimmed);
  writeStorage([trimmed, ...current].slice(0, MAX_RECENT));
}

export function clearRecent(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // silently ignore
  }
}
