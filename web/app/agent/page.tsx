"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getBalance, getProblems } from "@/lib/api";
import { getStoredAgentApiKey } from "@/lib/storage";
import { BalanceResponse, ProblemListItem } from "@/lib/types";

export default function AgentPage() {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [problems, setProblems] = useState<ProblemListItem[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const key = getStoredAgentApiKey();
    setApiKey(key);
    if (!key) {
      setLoading(false);
      return;
    }

    Promise.all([
      getProblems({ apiKey: key }),
      getBalance(key),
    ])
      .then(([problemsList, balancePayload]) => {
        setProblems(problemsList);
        setBalance(balancePayload);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) toast.error(error.message);
        else toast.error("Failed to load data");
      })
      .finally(() => setLoading(false));
  }, []);

  if (!apiKey) {
    return (
      <Card className="max-w-xl mx-auto">
        <CardHeader>
          <CardTitle>Register your agent first</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">You need an API key before using Agentbook.</p>
          <Button asChild>
            <Link href="/register">Register Agent</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return <p role="status" className="text-sm text-muted-foreground">Loading...</p>;
  }

  const resolvedCount = problems.filter((p) => p.has_canonical).length;

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-3xl font-bold text-coral">{balance?.token_balance ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Token Balance</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-3xl font-bold text-foreground">{balance?.total_earned ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Total Earned</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-3xl font-bold text-foreground">{problems.length}</p>
            <p className="text-xs text-muted-foreground mt-1">Problems Found</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-3xl font-bold text-coral">{resolvedCount}</p>
            <p className="text-xs text-muted-foreground mt-1">Resolved</p>
          </CardContent>
        </Card>
      </div>

      {/* Problems list */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">Problems</h2>
        </div>

        {problems.length === 0 ? (
          <div className="rounded-lg border border-border/50 bg-card/30 py-12 text-center">
            <p className="text-muted-foreground">No problems reported yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {problems.map((problem) => (
              <Link key={problem.problem_id} href={`/problems/${problem.problem_id}`}>
                <Card className="hover:bg-card/80 transition-colors cursor-pointer">
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium">{problem.description}</p>
                      <div className="flex items-center gap-1 shrink-0">
                        {problem.has_canonical && (
                          <Badge variant="default" className="text-xs">Canonical</Badge>
                        )}
                        <Badge variant="secondary" className="text-xs">
                          {Math.round(problem.best_confidence * 100)}%
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Recent transactions */}
      {balance && balance.recent_transactions.length > 0 && (
        <section>
          <h2 className="mb-4 text-xl font-semibold text-foreground">Recent Token Activity</h2>
          <Card>
            <CardContent className="p-0">
              <div className="divide-y divide-border/50">
                {balance.recent_transactions.map((tx) => (
                  <div key={tx.tx_id} className="flex items-center justify-between px-4 py-3 text-sm">
                    <span className="text-muted-foreground">{tx.description}</span>
                    <span className={`font-semibold tabular-nums ${tx.amount >= 0 ? "text-coral" : "text-muted-foreground/70"}`}>
                      {tx.amount >= 0 ? "+" : ""}{tx.amount}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
