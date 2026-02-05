"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

type VoteButtonsProps = {
  upvotes: number;
  downvotes: number;
  wilsonScore: number;
  onVote: (voteType: "upvote" | "downvote") => Promise<void>;
};

export function VoteButtons({
  upvotes,
  downvotes,
  wilsonScore,
  onVote,
}: VoteButtonsProps) {
  const [submitting, setSubmitting] = useState(false);
  const [hasVoted, setHasVoted] = useState(false);

  async function handleVote(voteType: "upvote" | "downvote") {
    if (hasVoted) {
      return;
    }
    setSubmitting(true);
    try {
      await onVote(voteType);
      setHasVoted(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={submitting || hasVoted}
        onClick={() => handleVote("upvote")}
      >
        Upvote
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={submitting || hasVoted}
        onClick={() => handleVote("downvote")}
      >
        Downvote
      </Button>
      <span className="text-sm text-muted-foreground">
        {upvotes - downvotes} · {(wilsonScore * 100).toFixed(1)}%
      </span>
    </div>
  );
}
