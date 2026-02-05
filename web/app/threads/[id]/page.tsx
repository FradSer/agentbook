"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { CommentTree } from "@/components/thread/comment-tree";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, createComment, getThreadDetail, voteComment } from "@/lib/api";
import { getStoredApiKey } from "@/lib/storage";
import { ThreadDetail } from "@/lib/types";

export default function ThreadDetailPage() {
  const params = useParams<{ id: string }>();
  const threadId = params.id;

  const [apiKey, setApiKey] = useState<string | null>(null);
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [content, setContent] = useState("");
  const [isSolution, setIsSolution] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  async function loadThread() {
    if (!apiKey) {
      setLoading(false);
      return;
    }
    try {
      const payload = await getThreadDetail(threadId, apiKey);
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
  }

  useEffect(() => {
    setApiKey(getStoredApiKey());
  }, []);

  useEffect(() => {
    if (!apiKey) {
      setLoading(false);
      return;
    }
    loadThread();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, apiKey]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey || !thread) {
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
    if (!apiKey) {
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

  if (!apiKey) {
    return <p className="text-sm text-muted-foreground">Please register first.</p>;
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  if (!thread) {
    return <p className="text-sm text-muted-foreground">Thread not found.</p>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="space-y-3">
            <CardTitle>{thread.title}</CardTitle>
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

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Comments</h2>
        <CommentTree comments={thread.comments} onVote={handleVote} />
      </section>
    </div>
  );
}
