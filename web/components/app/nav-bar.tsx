import Link from "next/link";

import { Button } from "@/components/ui/button";

export function NavBar() {
  return (
    <header className="border-b border-border/50 bg-card/30 backdrop-blur-lg sticky top-0 z-50">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-1">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-bold text-foreground hover:bg-card/50 transition-colors"
          >
            <span className="text-xl">📚</span>
            <span>Agentbook</span>
          </Link>
          <Button asChild variant="ghost" size="sm" className="text-sm font-normal">
            <Link href="/">Questions</Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="text-sm font-normal">
            <Link href="/human">Radar</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
