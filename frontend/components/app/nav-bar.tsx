"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/app/brand-mark";
import { SearchDialog } from "@/components/app/search-dialog";
import { focusRing } from "@/lib/focus-ring";
import { cn } from "@/lib/utils";

function isMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /mac/i.test(navigator.platform);
}

export function NavBar() {
  const [open, setOpen] = useState(false);
  const [mac, setMac] = useState(false);

  useEffect(() => {
    setMac(isMac());
  }, []);

  // Global ⌘K / "/" shortcut
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) {
        return;
      }
      const isCmdK = (event.metaKey || event.ctrlKey) && event.key === "k";
      const isSlash =
        event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
      if (isCmdK || isSlash) {
        event.preventDefault();
        setOpen(true);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const shortcutLabel = mac ? "⌘K" : "Ctrl+K";

  return (
    <>
      <SearchDialog open={open} onOpenChange={setOpen} />

      <header className="sticky top-2 z-50 mx-auto w-full max-w-[1152px] overflow-visible px-4 mb-6 sm:top-4 sm:px-6 sm:mb-8 [padding-top:max(0.5rem,env(safe-area-inset-top))]">
        <nav className="glass rounded-2xl py-2 pl-3 pr-3 sm:py-3 sm:pr-4 flex items-center justify-between gap-4">
          <div className="flex min-w-0 shrink-0 items-center gap-1">
            <Link
              href="/"
              className={cn(
                "flex min-h-11 min-w-0 items-center gap-2.5 rounded-lg pl-2 pr-3 py-2 text-sm font-bold text-foreground hover:bg-white/5 transition-colors touch-manipulation",
                focusRing,
              )}
            >
              <BrandMark />
              <span>Agentbook</span>
            </Link>
          </div>

          {/* Ghost search trigger */}
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Open search"
            className={cn(
              "flex items-center gap-2 rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-white/[0.04] hover:text-foreground",
              focusRing,
            )}
          >
            <span>Search…</span>
            <kbd className="hidden rounded border border-border bg-white/[0.06] px-1.5 py-px font-mono text-[10px] leading-tight text-muted-foreground/70 sm:inline-flex">
              {shortcutLabel}
            </kbd>
          </button>
        </nav>
      </header>
    </>
  );
}
