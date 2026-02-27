import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { MessageSquare, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ThreadListItem } from "@/lib/types";

type ThreadCardProps = {
  thread: ThreadListItem;
  onTagClick?: (tag: string) => void;
};

export function ThreadCard({ thread, onTagClick }: ThreadCardProps) {
  const answeredClass = thread.has_solution
    ? "bg-green-600 text-white border-green-600"
    : thread.comment_count > 0
      ? "border-green-500 text-green-700"
      : "border-border text-muted-foreground";

  return (
    <div className="flex gap-4 border-b py-4 last:border-b-0">
      {/* Stats column */}
      <div className="flex w-16 shrink-0 flex-col items-end gap-2 pt-0.5 text-sm">
        <div
          className={`flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${answeredClass}`}
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
      <div className="min-w-0 flex-1 space-y-1.5">
        <Link
          href={`/threads/${thread.thread_id}`}
          className="text-base font-medium text-blue-600 hover:text-blue-800 hover:underline"
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
                className="inline-flex h-5 items-center rounded bg-blue-50 px-1.5 text-xs text-blue-700 hover:bg-blue-100"
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
  );
}
