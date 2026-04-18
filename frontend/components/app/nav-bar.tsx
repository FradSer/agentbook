import Link from "next/link";

import { BrandMark } from "@/components/app/brand-mark";
import { SearchBox } from "@/components/app/search-box";
import { focusRing } from "@/lib/focus-ring";
import { cn } from "@/lib/utils";

export function NavBar() {
  return (
    <header className="sticky top-2 z-50 mx-auto w-full max-w-[1152px] overflow-visible px-4 mb-6 sm:top-4 sm:px-6 sm:mb-8 [padding-top:max(0.5rem,env(safe-area-inset-top))]">
      <nav className="glass rounded-2xl py-2 pl-3 pr-3 sm:py-3 sm:pr-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
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
        <div className="min-w-0 w-full sm:max-w-xl sm:shrink">
          <SearchBox variant="hero" />
        </div>
      </nav>
    </header>
  );
}
