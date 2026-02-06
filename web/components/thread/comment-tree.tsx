"use client";

import { formatDistanceToNow } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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

  roots.sort((a, b) => b.wilson_score - a.wilson_score);
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
  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span>{formatDistanceToNow(new Date(node.created_at), { addSuffix: true })}</span>
              {node.is_solution ? <Badge>Solution</Badge> : null}
            </div>
            {onVote ? (
              <VoteButtons
                upvotes={node.upvotes}
                downvotes={node.downvotes}
                wilsonScore={node.wilson_score}
                onVote={(voteType) => onVote(node.comment_id, voteType)}
              />
            ) : (
              <span className="text-sm text-muted-foreground">
                {node.upvotes - node.downvotes} · {(node.wilson_score * 100).toFixed(1)}%
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <p>{node.content}</p>
        </CardContent>
      </Card>
      {node.children.length > 0 ? (
        <div className="space-y-3 border-l pl-4" style={{ marginLeft: depth * 8 }}>
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
    return <p className="text-sm text-muted-foreground">No comments yet.</p>;
  }

  return (
    <div className="space-y-4">
      {roots.map((root) => (
        <CommentNodeItem key={root.comment_id} node={root} depth={0} onVote={onVote} />
      ))}
    </div>
  );
}
