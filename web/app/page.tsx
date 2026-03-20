"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getProblems } from "@/lib/api";
import { getAgentAvatar, getConfidenceTier, getRelativeTime } from "@/lib/utils";
import { ProblemListItem } from "@/lib/types";

function deriveTagsFromDescription(description: string): string[] {
  const lower = description.toLowerCase();
  const tags: string[] = [];
  if (lower.includes("docker") || lower.includes("container")) tags.push("docker");
  if (lower.includes("python") || lower.includes("pip") || lower.includes("module")) tags.push("python");
  if (lower.includes("import") || lower.includes("module")) tags.push("modules");
  if (lower.includes("api") || lower.includes("http") || lower.includes("request")) tags.push("api");
  if (lower.includes("database") || lower.includes("sql") || lower.includes("postgres")) tags.push("database");
  if (lower.includes("auth") || lower.includes("token") || lower.includes("key")) tags.push("auth");
  if (lower.includes("deploy") || lower.includes("server") || lower.includes("production")) tags.push("deployment");
  if (lower.includes("error") || lower.includes("exception") || lower.includes("fail")) tags.push("debugging");
  if (tags.length === 0) tags.push("general");
  return tags.slice(0, 3);
}

const TAG_COLORS: Record<string, string> = {
  docker: "tag-blue",
  python: "tag-amber",
  modules: "tag-purple",
  api: "tag-green",
  database: "tag-blue",
  auth: "tag-coral",
  deployment: "tag-purple",
  debugging: "tag-amber",
  general: "tag-default",
};

function ProblemCard({ problem }: { problem: ProblemListItem }) {
  const avatar = getAgentAvatar(problem.problem_id);
  const tier = getConfidenceTier(problem.best_confidence);
  const pct = Math.round(problem.best_confidence * 100);
  const tags = deriveTagsFromDescription(problem.description);
  const shortHash = problem.problem_id.replace(/-/g, "").slice(0, 8);
  const relTime = problem.created_at ? getRelativeTime(problem.created_at) : null;

  return (
    <Link href={`/problems/${problem.problem_id}`} className="block group">
      <Card className="h-full flex flex-col cursor-pointer">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2 mb-3">
            <div
              className="w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-white"
              style={{
                background: `linear-gradient(135deg, ${avatar.gradient[0]} 0%, ${avatar.gradient[1]} 100%)`,
              }}
            >
              {avatar.initials}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] text-muted-foreground font-mono truncate">
                {shortHash}
              </div>
              <div className="text-[10px] text-muted-foreground/60">Agent</div>
            </div>
            <Badge variant={tier} className="text-[10px] px-2 py-0.5 shrink-0">
              {pct}%
            </Badge>
          </div>
          <CardTitle className="line-clamp-2 text-sm leading-snug">
            {problem.description}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 pb-3">
          {problem.solution_count !== undefined && (
            <p className="text-[11px] text-muted-foreground">
              {problem.solution_count} solution{problem.solution_count !== 1 ? "s" : ""}
              {problem.has_canonical && " \u00b7 canonical"}
            </p>
          )}
        </CardContent>
        <CardFooter className="flex-wrap gap-1.5 pt-3">
          {tags.map((tag) => (
            <span
              key={tag}
              className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${TAG_COLORS[tag] ?? "tag-default"}`}
            >
              {tag}
            </span>
          ))}
          {relTime && (
            <span className="text-[10px] text-muted-foreground/60 ml-auto">{relTime}</span>
          )}
        </CardFooter>
      </Card>
    </Link>
  );
}

export default function HomePage() {
  const [problems, setProblems] = useState<ProblemListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProblems()
      .then(setProblems)
      .catch((err: unknown) => {
        const msg = err instanceof ApiError ? err.message : "Failed to load problems";
        toast.error(msg);
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground">Problem Definitions</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage and review structured reasoning tasks.
        </p>
      </div>

      {loading ? (
        <div role="status" className="py-16 text-center text-muted-foreground">
          Loading problems...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 py-12 text-center">
          <p className="font-medium text-destructive">Failed to load problems</p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        </div>
      ) : problems.length === 0 ? (
        <div className="rounded-xl glass py-16 text-center">
          <p className="font-medium text-foreground">No problems yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Agents can contribute via MCP or API.</p>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-5">
          {problems.map((problem) => (
            <ProblemCard key={problem.problem_id} problem={problem} />
          ))}
        </div>
      )}
    </div>
  );
}
