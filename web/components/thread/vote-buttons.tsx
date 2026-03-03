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
    <div className="flex flex-col items-center gap-0.5">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 rounded-full text-muted-foreground hover:text-orange-500 hover:bg-orange-50"
        disabled={submitting || hasVoted}
        onClick={() => handleVote("upvote")}
        aria-label="Upvote"
      >
        <ChevronUp className="h-5 w-5" />
      </Button>
      <span
        className={`w-8 text-center text-base font-semibold tabular-nums leading-tight ${
          score > 0
            ? "text-green-600"
            : score < 0
              ? "text-red-500"
              : "text-muted-foreground"
        }`}
      >
        {score}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 rounded-full text-muted-foreground hover:text-blue-500 hover:bg-blue-50"
        disabled={submitting || hasVoted}
        onClick={() => handleVote("downvote")}
        aria-label="Downvote"
      >
        <ChevronDown className="h-5 w-5" />
      </Button>
    </div>
  );
}
