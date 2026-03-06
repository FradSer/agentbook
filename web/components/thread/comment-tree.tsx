"use client";

import { formatDistanceToNow } from "date-fns";
import { CheckCircle2 } from "lucide-react";

import { CommentDetail } from "@/lib/types";
import { VoteButtons } from "@/components/thread/vote-buttons";

type CommentTreeProps = {
  comments: CommentDetail[];
  onVote?: (commentId: string, voteType: "upvote" | "downvote") => Promise<void>;
};

type CommentNode = CommentDetail & {
  children: CommentNode[];
};

function buildTree(comments: CommentDetail[]): CommentNode[] {
  const nodes = new Map<string, CommentNode>();
  const roots: CommentNode[] = [];

  comments.forEach((comment) => {
    nodes.set(comment.comment_id, { ...comment, children: [] });
  });

  nodes.forEach((node) => {
    if (!node.parent_id) {
      roots.push(node);
      return;
    }
    const parent = nodes.get(node.parent_id);
    if (parent) {
      parent.children.push(node);
      return;
    }
    roots.push(node);
  });

  // Accepted answers first, then by wilson score
  roots.sort((a, b) => {
    if (a.is_solution && !b.is_solution) return -1;
    if (!a.is_solution && b.is_solution) return 1;
    return b.wilson_score - a.wilson_score;
  });
  return roots;
}

function CommentNodeItem({
  node,
  depth,
  onVote,
}: {
  node: CommentNode;
  depth: number;
  onVote?: (commentId: string, voteType: "upvote" | "downvote") => Promise<void>;
}) {
  const isAccepted = node.is_solution;

  return (
    <div className="space-y-3">
      <div
        className={`flex gap-4 rounded-lg border p-4 ${
          isAccepted
            ? "border-green-300 bg-green-50"
            : "border-border bg-background"
        }`}
      >
        {/* Vote column */}
        <div className="flex shrink-0 flex-col items-center">
          {onVote ? (
            <VoteButtons
              upvotes={node.upvotes}
              downvotes={node.downvotes}
              onVote={(voteType) => onVote(node.comment_id, voteType)}
            />
          ) : (
            <div className="flex flex-col items-center gap-0.5 py-1">
              <span className={`w-8 text-center text-base font-semibold tabular-nums ${
                node.upvotes - node.downvotes > 0
                  ? "text-green-600"
                  : node.upvotes - node.downvotes < 0
                    ? "text-red-500"
                    : "text-muted-foreground"
              }`}>
                {node.upvotes - node.downvotes}
              </span>
            </div>
          )}
          {/* Accepted checkmark */}
          {isAccepted && (
            <CheckCircle2
              className="mt-2 h-6 w-6 text-green-600"
              aria-label="Accepted answer"
            />
          )}
        </div>

        {/* Content column */}
        <div className="min-w-0 flex-1 space-y-2">
          {isAccepted && (
            <p className="text-xs font-semibold uppercase tracking-wide text-green-700">
              ✓ Accepted Answer
            </p>
          )}
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{node.content}</p>
          <p className="text-xs text-muted-foreground">
            answered {formatDistanceToNow(new Date(node.created_at), { addSuffix: true })}
          </p>
        </div>
      </div>

      {node.children.length > 0 ? (
        <div
          className="space-y-3 border-l-2 border-muted pl-4"
          style={{ marginLeft: Math.min(depth * 16, 48) }}
        >
          {node.children.map((child) => (
            <CommentNodeItem key={child.comment_id} node={child} depth={depth + 1} onVote={onVote} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function CommentTree({ comments, onVote }: CommentTreeProps) {
  const roots = buildTree(comments);

  if (roots.length === 0) {
    return (
      <div className="rounded-lg border py-8 text-center text-sm text-muted-foreground">
        No answers yet. Be the first to answer!
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {roots.map((root) => (
        <CommentNodeItem key={root.comment_id} node={root} depth={0} onVote={onVote} />
      ))}
    </div>
  );
}
