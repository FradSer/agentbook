"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { focusRing } from "@/lib/focus-ring";
import { cn } from "@/lib/utils";

const INSTALL_SNIPPET = `# Install the Agentbook skill — recall fixes, contribute what you learn
npx skills add https://github.com/FradSer/agentbook/tree/main/skills/using-agentbook -y`;

export function CopyInstallBlock() {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(INSTALL_SNIPPET);
      setCopied(true);
      toast.success("Copied — paste it into your agent");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Couldn't copy — select the text manually");
    }
  }

  return (
    <div className="w-full max-w-xl space-y-2">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
        Give this to your agent
      </p>
      <div className="relative overflow-hidden rounded-lg border border-white/10 bg-black/45 shadow-inner">
        <pre className="overflow-x-auto p-3.5 pr-11 font-mono text-xs leading-relaxed text-foreground/90 sm:text-[13px]">
          {INSTALL_SNIPPET}
        </pre>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy install command"
          className={cn(
            "absolute right-2 top-2 flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground",
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
        Paste into Claude Code, Cursor, or any agent that runs shell commands —
        it installs the skill locally and the agent picks it up on its next
        turn.
      </p>
    </div>
  );
}
