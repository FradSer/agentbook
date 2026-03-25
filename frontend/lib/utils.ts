import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

function hashStringToUint32(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  return hash >>> 0;
}

/** Deterministic diagonal gradient stops (HSL) from any string seed. */
export function gradientFromSeed(seed: string): { from: string; to: string } {
  const h = hashStringToUint32(seed);
  const hue1 = h % 360;
  const offset = 24 + ((h >>> 8) % 25);
  const hue2 = (hue1 + offset) % 360;
  const sat1 = 55 + (h % 18);
  const sat2 = 55 + ((h >>> 16) % 18);
  const light1 = 48 + ((h >>> 4) % 11);
  const light2 = 48 + ((h >>> 12) % 11);
  return {
    from: `hsl(${hue1} ${sat1}% ${light1}%)`,
    to: `hsl(${hue2} ${sat2}% ${light2}%)`,
  };
}

const _avatarCache = new Map<string, { gradient: string[] }>();

export function getAgentAvatar(id: string): { gradient: string[] } {
  const cached = _avatarCache.get(id);
  if (cached) return cached;
  const { from, to } = gradientFromSeed(id);
  const result = { gradient: [from, to] };
  _avatarCache.set(id, result);
  return result;
}

const _rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function getRelativeTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    if (Number.isNaN(date.getTime())) return "";

    const diffSec = Math.round((date.getTime() - Date.now()) / 1000);
    const abs = Math.abs(diffSec);

    if (abs >= 86400 * 365) {
      return _rtf.format(Math.round(diffSec / (86400 * 365)), "year");
    }
    if (abs >= 86400 * 30) {
      return _rtf.format(Math.round(diffSec / (86400 * 30)), "month");
    }
    if (abs >= 86400 * 7) {
      return _rtf.format(Math.round(diffSec / (86400 * 7)), "week");
    }
    if (abs >= 86400) {
      return _rtf.format(Math.round(diffSec / 86400), "day");
    }
    if (abs >= 3600) {
      return _rtf.format(Math.round(diffSec / 3600), "hour");
    }
    if (abs >= 60) {
      return _rtf.format(Math.round(diffSec / 60), "minute");
    }
    return _rtf.format(diffSec, "second");
  } catch {
    return "";
  }
}

export function getConfidenceTier(confidence: number): "high" | "med" | "low" {
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.4) return "med";
  return "low";
}

/** Shorten OpenRouter-style model ids for inline UI; full string in title attribute. */
export function formatLlmModelLabel(model: string | null | undefined, maxLen = 42): string | null {
  if (!model || !model.trim()) return null;
  const t = model.trim();
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1)}…`;
}

export const TAG_COLORS: Record<string, string> = {
  docker: "tag-blue",
  python: "tag-amber",
  modules: "tag-purple",
  api: "tag-green",
  database: "tag-blue",
  auth: "tag-coral",
  deployment: "tag-purple",
  debugging: "tag-amber",
  general: "tag-default",
};
