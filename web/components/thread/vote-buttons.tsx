"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

type VoteButtonsProps = {
  upvotes: number;
  downvotes: number;
  onVote: (voteType: "upvote" | "downvote") => Promise<void>;
};

export function VoteButtons({
  upvotes,
  downvotes,
  onVote,
}: VoteButtonsProps) {
  const [submitting, setSubmitting] = useState(false);
  const [hasVoted, setHasVoted] = useState(false);
  const score = upvotes - downvotes;

  async function handleVote(voteType: "upvote" | "downvote") {
    if (hasVoted) return;
    setSubmitting(true);
    try {
      await onVote(voteType);
      setHasVoted(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9 rounded-full text-muted-foreground hover:text-coral hover:bg-coral/10 transition-all"
        disabled={submitting || hasVoted}
        onClick={() => handleVote("upvote")}
        aria-label="Upvote"
      >
        <ChevronUp className="h-5 w-5" />
      </Button>
      <span
        className={`w-10 text-center text-lg font-bold tabular-nums leading-tight ${
          score > 0
            ? "text-coral"
            : score < 0
              ? "text-muted-foreground/70"
              : "text-muted-foreground"
        }`}
      >
        {score}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9 rounded-full text-muted-foreground hover:text-muted-foreground/70 hover:bg-secondary transition-all"
        disabled={submitting || hasVoted}
        onClick={() => handleVote("downvote")}
        aria-label="Downvote"
      >
        <ChevronDown className="h-5 w-5" />
      </Button>
    </div>
  );
}
