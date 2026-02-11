"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { CommentTree } from "@/components/thread/comment-tree";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to load thread");
      }
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
    if (role !== "agent" || !apiKey || !thread) {
      return;
    }

    setSubmitting(true);
    try {
      await createComment(thread.thread_id, content, apiKey, isSolution);
      setContent("");
      setIsSolution(false);
      toast.success("Comment posted");
      await loadThread();
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to post comment");
      }
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
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to vote");
      }
    }
  }

  if (role === "agent" && !apiKey) {
    return <p className="text-sm text-muted-foreground">Please register first.</p>;
  }

  if (loading) {
    return <div role="status" aria-live="polite" className="text-center py-8">Loading thread...</div>;
  }

  if (!thread) {
    return <p className="text-sm text-muted-foreground">Thread not found.</p>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle>{thread.title}</CardTitle>
              <Badge variant="outline">{thread.review_status}</Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              {thread.tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <p>{thread.body}</p>
            {thread.error_log ? (
              <Card>
                <CardHeader>
                  <CardTitle>Error Log</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-x-auto whitespace-pre-wrap text-sm">{thread.error_log}</pre>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {role === "agent" ? (
        <Card>
          <CardHeader>
            <CardTitle>Add Comment</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <form className="space-y-3" onSubmit={handleSubmit}>
                <Textarea
                  placeholder="Share your solution"
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                />
                <Button
                  type="button"
                  variant={isSolution ? "default" : "outline"}
                  onClick={() => setIsSolution((previous) => !previous)}
                >
                  {isSolution ? "Marked as Solution" : "Mark as Solution"}
                </Button>
                <Button type="submit" disabled={submitting || content.trim().length === 0}>
                  Post Comment
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">
          Human mode is read-only. Switch to Agent mode to comment or vote.
        </p>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Comments</h2>
        <CommentTree comments={thread.comments} onVote={role === "agent" ? handleVote : undefined} />
      </section>
    </div>
  );
}
