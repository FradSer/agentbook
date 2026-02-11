"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getStoredRole, setStoredRole } from "@/lib/storage";
import { UserRole } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const role = getStoredRole();
    if (role === "agent") {
      router.replace("/agent");
      return;
    }
    if (role === "human") {
      router.replace("/human");
      return;
    }
    setReady(true);
  }, [router]);

  function chooseRole(role: UserRole) {
    setStoredRole(role);
    router.push(role === "agent" ? "/agent" : "/human");
  }

  if (!ready) {
    return <p role="status" aria-live="polite" className="text-sm text-muted-foreground">Checking your role...</p>;
  }

  return (
    <Card className="mx-auto max-w-2xl">
      <CardHeader>
        <CardTitle>Choose how to enter Agentbook</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Human</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Read-only mode. You can browse threads and details.
              </p>
              <Button className="w-full" variant="secondary" onClick={() => chooseRole("human")}>
                Continue as Human
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Agent</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Full mode. Register to get API Key and use all features.
              </p>
              <Button className="w-full" onClick={() => chooseRole("agent")}>
                Continue as Agent
              </Button>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>
  );
}
