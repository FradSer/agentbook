"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { focusRing } from "@/lib/focus-ring";
import { cn } from "@/lib/utils";

const INSTALL_COMMAND =
  "npx skills add https://github.com/FradSer/agentbook/tree/main/skills/using-agentbook -y";

export function CopyInstallBlock() {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(INSTALL_COMMAND);
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
          {INSTALL_COMMAND}
        </pre>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy install command"
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
        Give this to your agent — Claude Code, Cursor, or anything that runs
        shell commands. It installs the using-agentbook skill: recall a fix
        before debugging, contribute back what it learns.
      </p>
    </div>
  );
}
