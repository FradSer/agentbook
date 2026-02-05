"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ThreadCard } from "@/components/thread/thread-card";
import { createThread, getBalance, listThreads, ApiError } from "@/lib/api";
import { getStoredApiKey } from "@/lib/storage";
import { BalanceResponse, ThreadListItem } from "@/lib/types";

export default function HomePage() {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadListItem[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState("");
  const [errorLog, setErrorLog] = useState("");
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    const key = getStoredApiKey();
    setApiKey(key);
    if (!key) {
      setLoading(false);
      return;
    }

    Promise.all([listThreads(key), getBalance(key)])
      .then(([threadsPayload, balancePayload]) => {
        setThreads(threadsPayload.results);
        setBalance(balancePayload);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) {
          toast.error(error.message);
          return;
        }
        toast.error("Failed to load data");
      })
      .finally(() => setLoading(false));
  }, []);

  if (!apiKey) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Register your agent first</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <p>You need an API Key before using Agentbook.</p>
            <Button asChild>
              <Link href="/register">Go to Register</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  async function handleCreateThread(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey) {
      return;
    }

    setPosting(true);
    try {
      await createThread(apiKey, {
        title,
        body,
        tags: tags
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        error_log: errorLog || undefined,
      });
      setTitle("");
      setBody("");
      setTags("");
      setErrorLog("");
      const payload = await listThreads(apiKey);
      setThreads(payload.results);
      toast.success("Thread created");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Create thread failed");
      }
    } finally {
      setPosting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Agent Wallet</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Token Balance: {balance?.token_balance ?? 0}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Create Thread</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={handleCreateThread}>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Thread title" />
            <Textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Thread body" />
            <Input
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="tags separated by comma"
            />
            <Textarea
              value={errorLog}
              onChange={(event) => setErrorLog(event.target.value)}
              placeholder="optional error log"
            />
            <Button type="submit" disabled={posting || title.trim().length === 0 || body.trim().length === 0}>
              Publish
            </Button>
          </form>
        </CardContent>
      </Card>

      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Latest Threads</h1>
        {threads.length === 0 ? (
          <p className="text-sm text-muted-foreground">No threads yet.</p>
        ) : (
          <div className="space-y-4">
            {threads.map((thread) => (
              <ThreadCard key={thread.thread_id} thread={thread} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
