import { formatDistanceToNow } from "date-fns";
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const AVATAR_GRADIENTS = [
  ["#4ade80", "#22c55e"],
  ["#60a5fa", "#3b82f6"],
  ["#a78bfa", "#8b5cf6"],
  ["#fb923c", "#f97316"],
  ["#f472b6", "#ec4899"],
  ["#34d399", "#10b981"],
  ["#818cf8", "#6366f1"],
  ["#fbbf24", "#f59e0b"],
];

export function getAgentAvatar(id: string): { gradient: string[]; initials: string } {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash + id.charCodeAt(i)) | 0;
  }
  const index = Math.abs(hash) % AVATAR_GRADIENTS.length;
  const short = id.replace(/-/g, "").slice(0, 2).toUpperCase();
  return { gradient: AVATAR_GRADIENTS[index], initials: short };
}

export function getRelativeTime(dateStr: string): string {
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
  } catch {
    return "";
  }
}

export function getConfidenceTier(confidence: number): "high" | "med" | "low" {
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.4) return "med";
  return "low";
}
