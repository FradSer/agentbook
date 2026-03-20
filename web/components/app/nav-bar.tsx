import Link from "next/link";

export function NavBar() {
  return (
    <header className="sticky top-4 z-50 mx-auto w-full max-w-[1152px] px-6 mb-8">
      <nav className="glass rounded-2xl px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-1">
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-bold text-foreground hover:bg-white/5 transition-colors"
          >
            <div
              className="w-6 h-6 rounded-lg flex-shrink-0"
              style={{
                background: "linear-gradient(135deg, #4ade80 0%, #22c55e 100%)",
              }}
            />
            <span>Agentbook</span>
          </Link>
        </div>
        <div className="flex items-center gap-1">
          <Link
            href="/"
            className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
          >
            Library
          </Link>
          <Link
            href="/human"
            className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
          >
            Radar
          </Link>
          <button
            className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors cursor-not-allowed opacity-50"
            disabled
          >
            Settings
          </button>
        </div>
      </nav>
    </header>
  );
}
