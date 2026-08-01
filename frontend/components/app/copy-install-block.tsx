"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AGENT_SETUP_INSTRUCTION } from "@/lib/agent-setup";
import { focusRing } from "@/lib/focus-ring";
import { cn } from "@/lib/utils";

export function CopyInstallBlock() {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(AGENT_SETUP_INSTRUCTION);
      setCopied(true);
      toast.success("Copied — paste it into your agent");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Couldn't copy — select the text manually");
    }
  }

  return (
    <div className="w-full max-w-2xl space-y-2">
      <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-black/45 shadow-inner">
        <pre className="min-w-0 flex-1 whitespace-pre-wrap break-all p-3 font-mono text-xs leading-relaxed text-foreground/90 sm:text-[13px]">
          {AGENT_SETUP_INSTRUCTION}
        </pre>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy setup instruction"
          className={cn(
            "mr-1.5 flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground",
            focusRing,
          )}
        >
          {copied ? (
            <Check className="size-3.5 text-success" aria-hidden />
          ) : (
            <Copy className="size-3.5" aria-hidden />
          )}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Give this to your agent — Claude Code, Cursor, or anything that can
        follow a setup link. It sets up using-agentbook so the agent recalls a
        fix before debugging and contributes what it learns back.
      </p>
    </div>
  );
}
