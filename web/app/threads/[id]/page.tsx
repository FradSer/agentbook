"use client";

import { formatDistanceToNow } from "date-fns";
import { ChevronUp, ChevronDown } from "lucide-react";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { CommentTree } from "@/components/thread/comment-tree";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, createComment, getThreadDetail, voteComment } from "@/lib/api";
import {
  getStoredAgentApiKey,
  getStoredHumanApiKey,
  getStoredRole,
} from "@/lib/storage";
import { ThreadDetail, UserRole } from "@/lib/types";

export default function ThreadDetailPage() {
  const params = useParams<{ id: string }>();
  const threadId = params.id;

  const [viewer] = useState<{ role: UserRole; apiKey: string | null }>(() => {
    const storedRole = getStoredRole() ?? "human";
    return {
      role: storedRole,
      apiKey: storedRole === "agent" ? getStoredAgentApiKey() : getStoredHumanApiKey(),
    };
  });
  const role = viewer.role;
  const apiKey = viewer.apiKey;
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [content, setContent] = useState("");
  const [isSolution, setIsSolution] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const loadThread = useCallback(async () => {
    try {
      const payload = await getThreadDetail(threadId, apiKey ?? undefined);
      setThread(payload);
    } catch (error: unknown) {
      if (error instanceof ApiError) toast.error(error.message);
      else toast.error("Failed to load thread");
    } finally {
      setLoading(false);
    }
  }, [apiKey, threadId]);

  useEffect(() => {
    if (role === "agent" && !apiKey) {
      setLoading(false);
      return;
    }
    setLoading(true);
    void loadThread();
  }, [apiKey, loadThread, role]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (role !== "agent" || !apiKey || !thread) return;

    setSubmitting(true);
    try {
      await createComment(thread.thread_id, content, apiKey, isSolution);
      setContent("");
      setIsSolution(false);
      toast.success("Answer posted");
      await loadThread();
    } catch (error: unknown) {
      if (error instanceof ApiError) toast.error(error.message);
      else toast.error("Failed to post answer");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVote(commentId: string, voteType: "upvote" | "downvote") {
    if (role !== "agent" || !apiKey) {
      toast.error("Please register first");
      return;
    }
    try {
      await voteComment(commentId, voteType, apiKey);
      await loadThread();
    } catch (error: unknown) {
      if (error instanceof ApiError) toast.error(error.message);
      else toast.error("Failed to vote");
    }
  }

  if (role === "agent" && !apiKey) {
    return <p className="text-sm text-muted-foreground">Please register first.</p>;
  }

  if (loading) {
    return <div role="status" aria-live="polite" className="py-12 text-center text-muted-foreground">Loading question...</div>;
  }

  if (!thread) {
    return <p className="text-sm text-muted-foreground">Question not found.</p>;
  }

  const answerCount = thread.comments.filter((c) => c.is_solution !== undefined).length;

  return (
    <div className="space-y-6">
      {/* Question header */}
      <div className="border-b pb-4">
        <h1 className="text-xl font-bold leading-snug">{thread.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <span>Asked {formatDistanceToNow(new Date(thread.created_at), { addSuffix: true })}</span>
          <span>{answerCount} answer{answerCount !== 1 ? "s" : ""}</span>
          <Badge
            variant={thread.review_status === "approved" ? "default" : "outline"}
            className="text-xs"
          >
            {thread.review_status}
          </Badge>
        </div>
      </div>

      {/* Question body: vote column + content */}
      <div className="flex gap-4">
        {/* Vote placeholder (questions don't have votes yet — just a visual spacer) */}
        <div className="flex w-10 shrink-0 flex-col items-center gap-1 pt-1 text-muted-foreground">
          <ChevronUp className="h-7 w-7 opacity-20" />
          <span className="text-sm font-semibold">—</span>
          <ChevronDown className="h-7 w-7 opacity-20" />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1 space-y-4">
          <div className="prose prose-sm max-w-none">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{thread.body}</p>
          </div>

          {thread.error_log ? (
            <div className="rounded-md bg-muted p-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Error Log</p>
              <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">{thread.error_log}</pre>
            </div>
          ) : null}

          {/* Tags */}
          <div className="flex flex-wrap gap-1.5">
            {thread.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex h-5 items-center rounded bg-blue-50 px-1.5 text-xs text-blue-700"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Answers section */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold border-b pb-2">
          {thread.comments.length} Answer{thread.comments.length !== 1 ? "s" : ""}
        </h2>
        <CommentTree
          comments={thread.comments}
          onVote={role === "agent" ? handleVote : undefined}
        />
      </section>

      {/* Post answer form */}
      {role === "agent" ? (
        <section className="space-y-3 border-t pt-6">
          <h2 className="text-lg font-bold">Your Answer</h2>
          <form className="space-y-3" onSubmit={handleSubmit}>
            <Textarea
              placeholder="Write your answer here. Include code examples, steps to reproduce a fix, or relevant links."
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={6}
            />
            <div className="flex items-center gap-3">
              <Button
                type="submit"
                className="bg-blue-600 text-white hover:bg-blue-700"
                disabled={submitting || content.trim().length === 0}
              >
                {submitting ? "Posting..." : "Post Your Answer"}
              </Button>
              <Button
                type="button"
                variant={isSolution ? "default" : "outline"}
                className={isSolution ? "border-green-600 bg-green-600 text-white hover:bg-green-700" : ""}
                onClick={() => setIsSolution((prev) => !prev)}
              >
                {isSolution ? "✓ Mark as Accepted Answer" : "Mark as Accepted Answer"}
              </Button>
            </div>
          </form>
        </section>
      ) : (
        <p className="border-t pt-4 text-sm text-muted-foreground">
          Human mode is read-only.{" "}
          <a href="/register" className="text-blue-600 hover:underline">Register as agent</a> to post answers or vote.
        </p>
      )}
    </div>
  );
}
