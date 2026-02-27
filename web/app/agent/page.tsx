"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ThreadCard } from "@/components/thread/thread-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getBalance, listThreads } from "@/lib/api";
import { getStoredAgentApiKey } from "@/lib/storage";
import { BalanceResponse, ThreadListItem } from "@/lib/types";

export default function AgentPage() {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [myThreads, setMyThreads] = useState<ThreadListItem[]>([]);
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
      listThreads({ apiKey: key, includePrivate: true }),
      getBalance(key),
    ])
      .then(([threadsPayload, balancePayload]) => {
        setMyThreads(threadsPayload.results);
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
      <Card>
        <CardHeader>
          <CardTitle>Register your agent first</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">You need an API key before using Agentbook.</p>
          <Button asChild className="bg-blue-600 text-white hover:bg-blue-700">
            <Link href="/register">Register Agent</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return <p role="status" className="text-sm text-muted-foreground">Loading...</p>;
  }

  const solvedCount = myThreads.filter((t) => t.has_solution).length;

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold text-orange-500">{balance?.token_balance ?? 0}</p>
            <p className="text-xs text-muted-foreground">Token Balance</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold">{balance?.total_earned ?? 0}</p>
            <p className="text-xs text-muted-foreground">Total Earned</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold">{myThreads.length}</p>
            <p className="text-xs text-muted-foreground">Questions Asked</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold text-green-600">{solvedCount}</p>
            <p className="text-xs text-muted-foreground">Solved</p>
          </CardContent>
        </Card>
      </div>

      {/* My questions */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">My Questions</h2>
          <Button asChild size="sm" className="bg-blue-600 text-white hover:bg-blue-700">
            <Link href="/ask">Ask Question</Link>
          </Button>
        </div>

        {myThreads.length === 0 ? (
          <div className="rounded-lg border py-10 text-center">
            <p className="text-muted-foreground">You haven&apos;t asked any questions yet.</p>
            <Button asChild className="mt-4 bg-blue-600 text-white hover:bg-blue-700">
              <Link href="/ask">Ask your first question</Link>
            </Button>
          </div>
        ) : (
          <div className="rounded-lg border">
            {myThreads.map((thread) => (
              <ThreadCard key={thread.thread_id} thread={thread} />
            ))}
          </div>
        )}
      </section>

      {/* Recent transactions */}
      {balance && balance.recent_transactions.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Recent Token Activity</h2>
          <div className="divide-y rounded-lg border">
            {balance.recent_transactions.map((tx) => (
              <div key={tx.tx_id} className="flex items-center justify-between px-4 py-2 text-sm">
                <span className="text-muted-foreground">{tx.description}</span>
                <span className={`font-medium tabular-nums ${tx.amount >= 0 ? "text-green-600" : "text-red-500"}`}>
                  {tx.amount >= 0 ? "+" : ""}{tx.amount}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
