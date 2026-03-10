import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { MessageSquare, CheckCircle2 } from "lucide-react";

import { ThreadListItem } from "@/lib/types";

type ThreadCardProps = {
  thread: ThreadListItem;
  onTagClick?: (tag: string) => void;
};

export function ThreadCard({ thread, onTagClick }: ThreadCardProps) {
  const answeredClass = thread.has_solution
    ? "bg-coral text-white border-coral shadow-sm"
    : thread.comment_count > 0
      ? "border-coral/50 text-coral bg-coral/10"
      : "border-border text-muted-foreground bg-secondary/50";

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 backdrop-blur-sm p-4 transition-all hover:border-border hover:bg-card/80">
      <div className="flex gap-4">
        {/* Stats column */}
        <div className="flex w-16 shrink-0 flex-col items-end gap-2 pt-0.5 text-sm">
          <div
            className={`flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-medium transition-all ${answeredClass}`}
            title={thread.has_solution ? "Has accepted answer" : `${thread.comment_count} answer(s)`}
          >
            {thread.has_solution ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <MessageSquare className="h-3 w-3" />
            )}
            <span>{thread.comment_count}</span>
          </div>
        </div>

        {/* Content column */}
        <div className="min-w-0 flex-1 space-y-2">
          <Link
            href={`/threads/${thread.thread_id}`}
            className="text-base font-semibold text-foreground hover:text-coral transition-colors"
          >
            {thread.title}
          </Link>
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {thread.body_preview}
          </p>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {thread.tags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => onTagClick?.(tag)}
                  className="inline-flex h-6 items-center rounded-full bg-secondary px-2.5 text-xs font-medium text-muted-foreground hover:bg-secondary/80 hover:text-foreground transition-colors"
                >
                  {tag}
                </button>
              ))}
            </div>
            <span className="shrink-0 text-xs text-muted-foreground">
              asked {formatDistanceToNow(new Date(thread.created_at), { addSuffix: true })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
