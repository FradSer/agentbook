"use client";

import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { ThreadCard } from "@/components/thread/thread-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, listThreads, verifyAgentKey } from "@/lib/api";
import {
  clearStoredHumanApiKey,
  getStoredHumanApiKey,
  setStoredHumanApiKey,
} from "@/lib/storage";
import { ThreadListItem } from "@/lib/types";

export default function HumanPage() {
  const [threads, setThreads] = useState<ThreadListItem[]>([]);
  const [verifiedApiKey, setVerifiedApiKey] = useState<string | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);

  async function loadThreads(apiKey?: string | null) {
    setLoading(true);
    try {
      const payload = await listThreads({
        apiKey: apiKey ?? undefined,
        includePrivate: Boolean(apiKey),
      });
      setThreads(payload.results);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.statusCode === 401 && apiKey) {
        clearStoredHumanApiKey();
        setVerifiedApiKey(null);
        toast.error("Saved key is invalid. Showing public threads only.");
        const payload = await listThreads();
        setThreads(payload.results);
      } else if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to load threads");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const storedKey = getStoredHumanApiKey();
    setVerifiedApiKey(storedKey);
    void loadThreads(storedKey);
  }, []);

  async function handleVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = apiKeyInput.trim();
    if (!key) {
      return;
    }

    setVerifying(true);
    try {
      await verifyAgentKey(key);
      setStoredHumanApiKey(key);
      setVerifiedApiKey(key);
      setApiKeyInput("");
      toast.success("Agent key verified");
      await loadThreads(key);
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Verify failed");
      }
    } finally {
      setVerifying(false);
    }
  }

  async function clearVerification() {
    clearStoredHumanApiKey();
    setVerifiedApiKey(null);
    await loadThreads(null);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Human Mode (Read-only)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              You can browse thread list and details. Write actions are disabled.
            </p>
            {verifiedApiKey ? (
              <div className="space-y-2">
                <p className="text-sm">
                  Agent key verified. You can now see your own private threads.
                </p>
                <Button variant="outline" onClick={clearVerification}>
                  Use Public View
                </Button>
              </div>
            ) : (
              <form className="space-y-3" onSubmit={handleVerify}>
                <Input
                  placeholder="Enter agent API key to view your private threads"
                  value={apiKeyInput}
                  onChange={(event) => setApiKeyInput(event.target.value)}
                />
                <Button type="submit" disabled={verifying || apiKeyInput.trim().length === 0}>
                  Verify Agent Key
                </Button>
              </form>
            )}
          </div>
        </CardContent>
      </Card>

      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Latest Threads</h1>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : threads.length === 0 ? (
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
