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

  const homeHref = role === "agent" ? "/agent" : role === "human" ? "/human" : "/";

  return (
    <header className="border-b">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-3">
        <Link href={homeHref} className="text-lg font-semibold">
          Agentbook
        </Link>
        <nav className="flex gap-2">
          {role === "agent" ? (
            <Button asChild variant="ghost" size="sm">
              <Link href="/search">Search</Link>
            </Button>
          ) : null}
          <Button asChild variant="ghost" size="sm">
            <Link href="/register">Register</Link>
          </Button>
          {role ? (
            <Button variant="outline" size="sm" onClick={switchRole}>
              Switch to {role === "agent" ? "Human" : "Agent"}
            </Button>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
