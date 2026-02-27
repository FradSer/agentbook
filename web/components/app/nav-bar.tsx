"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ROLE_CHANGED_EVENT, getStoredRole, setStoredRole } from "@/lib/storage";
import { UserRole } from "@/lib/types";

export function NavBar() {
  const router = useRouter();
  const [role, setRole] = useState<UserRole | null>(null);

  useEffect(() => {
    const syncRoleFromStorage = () => setRole(getStoredRole());
    syncRoleFromStorage();
    window.addEventListener("storage", syncRoleFromStorage);
    window.addEventListener(ROLE_CHANGED_EVENT, syncRoleFromStorage);
    return () => {
      window.removeEventListener("storage", syncRoleFromStorage);
      window.removeEventListener(ROLE_CHANGED_EVENT, syncRoleFromStorage);
    };
  }, []);

  function switchRole() {
    const nextRole: UserRole = role === "agent" ? "human" : "agent";
    setStoredRole(nextRole);
    setRole(nextRole);
    router.push(nextRole === "agent" ? "/agent" : "/human");
  }

  return (
    <header className="border-b bg-background">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-2">
        {/* Left: Logo + nav links */}
        <div className="flex items-center gap-1">
          <Link
            href="/"
            className="flex items-center gap-1.5 rounded px-2 py-1.5 text-sm font-bold text-orange-500 hover:bg-orange-50"
          >
            <span className="text-lg">📚</span>
            <span>Agentbook</span>
          </Link>
          <Button asChild variant="ghost" size="sm" className="text-sm font-normal">
            <Link href="/">Questions</Link>
          </Button>
          {role === "agent" ? (
            <Button asChild variant="ghost" size="sm" className="text-sm font-normal">
              <Link href="/agent">My Activity</Link>
            </Button>
          ) : null}
          {role === "human" ? (
            <Button asChild variant="ghost" size="sm" className="text-sm font-normal">
              <Link href="/human">Radar</Link>
            </Button>
          ) : null}
        </div>

        {/* Right: actions */}
        <nav className="flex items-center gap-2">
          {role === "agent" ? (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link href="/search">Search</Link>
              </Button>
              <Button asChild size="sm" className="bg-blue-600 text-white hover:bg-blue-700">
                <Link href="/ask">Ask Question</Link>
              </Button>
            </>
          ) : null}
          <Button asChild variant="ghost" size="sm">
            <Link href="/register">Register</Link>
          </Button>
          {role ? (
            <Button variant="outline" size="sm" onClick={switchRole}>
              {role === "agent" ? "Human View" : "Agent View"}
            </Button>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
