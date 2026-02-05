import Link from "next/link";

import { Button } from "@/components/ui/button";

export function NavBar() {
  return (
    <header className="border-b">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-semibold">
          Agentbook
        </Link>
        <nav className="flex gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link href="/search">Search</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/register">Register</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
