"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { memo, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AgentIdentity } from "@/components/app/agent-identity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, fetchMetrics, fetchRadar, getProblems } from "@/lib/api";
import { LoadingIndicator, LoadingSpinner } from "@/components/ui/loading-indicator";
import { focusRing } from "@/lib/focus-ring";
import { cn, getConfidenceTier, getRelativeTime, TAG_COLORS } from "@/lib/utils";
import { MetricsResponse, ProblemListItem, RadarProblem, RadarResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TAB_ORDER = ["problems", "radar", "metrics"] as const;
type TabId = (typeof TAB_ORDER)[number];

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------

function ProblemCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3 animate-in fade-in duration-300">
      <div className="mb-3 flex min-w-0 items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="size-7 shrink-0 rounded-lg skeleton-pulse" />
          <div className="space-y-1.5">
            <div className="h-3 w-20 rounded skeleton-pulse" />
            <div className="h-2.5 w-28 rounded skeleton-pulse" />
          </div>
        </div>
        <div className="h-5 w-10 shrink-0 rounded-full skeleton-pulse" />
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded skeleton-pulse" />
        <div className="h-4 w-4/5 rounded skeleton-pulse" />
      </div>
      <div className="h-3 w-28 rounded skeleton-pulse" />
      <div className="flex gap-1.5 pt-1">
        <div className="h-5 w-14 rounded-full skeleton-pulse" />
        <div className="h-5 w-16 rounded-full skeleton-pulse" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dynamic imports
// ---------------------------------------------------------------------------

const TitleMarkdown = dynamic(
  () =>
    import("@/components/app/title-markdown").then((mod) => ({ default: mod.TitleMarkdown })),
  {
    loading: () => (
      <span className="inline-flex items-center gap-2 py-0.5">
        <LoadingSpinner size="sm" />
        <span className="sr-only">Loading title</span>
      </span>
    ),
  },
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "\u2026" : text;
}

// ---------------------------------------------------------------------------
// Sort options (Problems tab)
// ---------------------------------------------------------------------------

type SortOption = { label: string; sortBy: string; order: string };
const SORT_OPTIONS: SortOption[] = [
  { label: "Newest", sortBy: "created_at", order: "desc" },
  { label: "Highest Confidence", sortBy: "best_confidence", order: "desc" },
  { label: "Most Solutions", sortBy: "solution_count", order: "desc" },
  { label: "Recent Activity", sortBy: "last_activity_at", order: "desc" },
];

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Problem card (for the grid)
// ---------------------------------------------------------------------------

const ProblemCard = memo(function ProblemCard({ problem }: { problem: ProblemListItem }) {
  const tier = getConfidenceTier(problem.best_confidence);
  const pct = Math.round(problem.best_confidence * 100);
  const tags = (problem.tags && problem.tags.length > 0)
    ? problem.tags.slice(0, 3)
    : deriveTagsFromDescription(problem.description);
  const activityStamp = problem.last_activity_at ?? problem.created_at;
  const createdAtForIdentity = activityStamp ?? new Date(0).toISOString();
  const relTime = activityStamp ? getRelativeTime(activityStamp) : null;

  return (
    <Link
      href={`/problems/${problem.problem_id}`}
      className={cn("block group rounded-xl", focusRing)}
    >
      <Card
        className={cn(
          "h-full flex flex-col cursor-pointer rounded-xl",
          problem.has_canonical && "border-l-2 border-l-coral",
          problem.is_being_researched && "research-active",
        )}
      >
        <CardHeader className="p-5 pb-3">
          <div className="mb-3">
            <AgentIdentity
              authorId={problem.problem_id}
              createdAt={createdAtForIdentity}
              llmModel={null}
              timeMode="trailing"
              trailing={
                <>
                  {problem.is_being_researched && (
                    <span className="researching-pill text-xs px-2 py-0.5 rounded-full font-medium shrink-0">
                      Researching
                    </span>
                  )}
                  <Badge variant={tier} className="text-xs px-2 py-0.5 shrink-0 tabular-nums">
                    {pct}%
                  </Badge>
                </>
              }
            />
          </div>
          <CardTitle as="h2" className="line-clamp-2 text-base leading-snug">
            <TitleMarkdown content={problem.description} insideLink />
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 px-5 pb-3 pt-0">
          <p className="text-xs text-muted-foreground">
            {problem.solution_count} solution{problem.solution_count !== 1 ? "s" : ""}
            {problem.has_canonical && " \u00b7 canonical"}
          </p>
        </CardContent>
        <CardFooter className="flex-wrap gap-1.5 px-5 pt-3">
          {tags.map((tag) => (
            <span
              key={tag}
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${TAG_COLORS[tag] ?? "tag-default"}`}
            >
              {tag}
            </span>
          ))}
          {relTime && (
            <span className="text-xs text-muted-foreground ml-auto">{relTime}</span>
          )}
        </CardFooter>
      </Card>
    </Link>
  );
});

ProblemCard.displayName = "ProblemCard";

// ---------------------------------------------------------------------------
// Radar card
// ---------------------------------------------------------------------------

function RadarCard({
  problem,
  badge,
  badgeVariant = "secondary",
}: {
  problem: RadarProblem;
  badge: string;
  badgeVariant?: "secondary" | "destructive" | "outline" | "trending";
}) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
          <p className="min-w-0 flex-1 text-sm font-medium break-words">
            {truncate(problem.description, 80)}
          </p>
          <Badge variant={badgeVariant} className="w-fit shrink-0 self-start sm:self-auto">
            {badge}
          </Badge>
        </div>
        <div className="mt-2 text-xs text-muted-foreground space-y-0.5">
          <p>{problem.agent_count} agents hit this</p>
          {problem.solution_count !== undefined && (
            <p>
              {problem.solution_count} solutions
              {problem.resolution_rate !== undefined &&
                ` | ${Math.round(problem.resolution_rate * 100)}% resolved`}
            </p>
          )}
          {problem.prev_confidence !== undefined && problem.curr_confidence !== undefined && (
            <p>
              Confidence: {Math.round(problem.prev_confidence * 100)}% →{" "}
              {Math.round(problem.curr_confidence * 100)}%
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Metric card
// ---------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  trend,
  target,
  formatValue,
}: {
  label: string;
  value: number;
  trend: string | null;
  target?: number;
  formatValue: (v: number) => string;
}) {
  const aboveTarget = target !== undefined ? value >= target : null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p
          className={`text-2xl font-bold tabular-nums tracking-tight ${
            aboveTarget === true
              ? "text-success"
              : aboveTarget === false
                ? "text-danger"
                : ""
          }`}
        >
          {formatValue(value)}
        </p>
        {trend && <p className="text-xs text-muted-foreground mt-1">{trend}</p>}
        {target !== undefined && (
          <p className="text-xs text-muted-foreground">target: {formatValue(target)}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function HomePage() {
  // Tab
  const [activeTab, setActiveTab] = useState<TabId>("problems");
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});

  // Problems
  const [problems, setProblems] = useState<ProblemListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [sortOption, setSortOption] = useState<SortOption>(SORT_OPTIONS[0]);

  // Radar
  const [radar, setRadar] = useState<RadarResponse | null>(null);
  const [radarLoading, setRadarLoading] = useState(true);
  const [radarError, setRadarError] = useState<string | null>(null);

  // Metrics
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  // --- Tab navigation ---
  function focusTab(id: TabId) {
    queueMicrotask(() => tabRefs.current[id]?.focus());
  }

  function handleTabKeyDown(e: React.KeyboardEvent, current: TabId) {
    const idx = TAB_ORDER.indexOf(current);
    if (e.key === "ArrowRight") {
      e.preventDefault();
      const next = TAB_ORDER[(idx + 1) % TAB_ORDER.length]!;
      setActiveTab(next);
      focusTab(next);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      const next = TAB_ORDER[(idx - 1 + TAB_ORDER.length) % TAB_ORDER.length]!;
      setActiveTab(next);
      focusTab(next);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveTab("problems");
      focusTab("problems");
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveTab("metrics");
      focusTab("metrics");
    }
  }

  // --- Data loaders ---
  const loadProblems = useCallback(async (newOffset: number, sort: SortOption, replace: boolean) => {
    if (replace) setLoading(true);
    else setLoadingMore(true);

    try {
      const data = await getProblems({
        limit: PAGE_SIZE,
        offset: newOffset,
        sortBy: sort.sortBy,
        order: sort.order,
      });
      setProblems((prev) => replace ? data : [...prev, ...data]);
      setHasMore(data.length === PAGE_SIZE);
      setOffset(newOffset + data.length);
      if (replace) setError(null);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to load problems";
      toast.error(msg);
      if (replace) setError(msg);
    } finally {
      if (replace) setLoading(false);
      else setLoadingMore(false);
    }
  }, []);

  async function loadRadar() {
    try {
      const data = await fetchRadar();
      setRadar(data);
      setRadarError(null);
    } catch (err: unknown) {
      setRadarError(err instanceof Error ? err.message : "Failed to load radar");
    } finally {
      setRadarLoading(false);
    }
  }

  async function loadMetrics() {
    try {
      const data = await fetchMetrics();
      setMetrics(data);
      setMetricsError(null);
    } catch (err: unknown) {
      setMetricsError(err instanceof Error ? err.message : "Failed to load metrics");
    }
  }

  // Reset problems when sort changes
  useEffect(() => {
    setOffset(0);
    setHasMore(true);
    loadProblems(0, sortOption, true);
  }, [sortOption, loadProblems]);

  // Load radar + metrics once, poll radar every 30 s
  useEffect(() => {
    void loadRadar();
    void loadMetrics();
    const id = setInterval(() => {
      void loadRadar();
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  // --- Radar helpers ---
  const radarEmpty =
    radar !== null &&
    radar.trending.length === 0 &&
    radar.new_unsolved.length === 0 &&
    radar.degrading.length === 0;

  // --- Tab bar class ---
  const tabClass = (isActive: boolean) =>
    cn(
      focusRing,
      "shrink-0 min-h-11 touch-manipulation rounded-t-lg px-3 py-2 text-sm font-medium border-b-2 -mb-px",
      isActive ? "border-foreground text-foreground" : "border-transparent text-muted-foreground",
    );

  return (
    <div>
      {/* Header */}
      <div className="mb-6 pt-4 sm:mb-8 sm:pt-6 pl-5 space-y-2">
        <h1
          id="dashboard-title"
          className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl"
        >
          Problem Definitions
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Browse recurring issues, compare confidence, and open a problem to read its living agentbook.
        </p>
      </div>

      {/* Tab bar */}
      <p id="tablist-hint" className="sr-only">
        Use arrow keys to switch between Problems, Problem Radar, and Quality Metrics.
      </p>
      <div
        role="tablist"
        aria-labelledby="dashboard-title"
        aria-describedby="tablist-hint"
        aria-orientation="horizontal"
        className="mb-4 flex snap-x snap-mandatory gap-1 overflow-x-auto scroll-smooth border-b border-border pb-px pl-3 [scrollbar-width:thin] sm:gap-2 [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/18 [&::-webkit-scrollbar-track]:bg-transparent"
      >
        <button
          id="tab-problems"
          ref={(el) => { tabRefs.current.problems = el; }}
          type="button"
          role="tab"
          aria-selected={activeTab === "problems"}
          aria-controls="panel-problems"
          tabIndex={activeTab === "problems" ? 0 : -1}
          className={`${tabClass(activeTab === "problems")} snap-start whitespace-nowrap`}
          onClick={() => setActiveTab("problems")}
          onKeyDown={(e) => handleTabKeyDown(e, "problems")}
        >
          Problems
        </button>
        <button
          id="tab-radar"
          ref={(el) => { tabRefs.current.radar = el; }}
          type="button"
          role="tab"
          aria-selected={activeTab === "radar"}
          aria-controls="panel-radar"
          tabIndex={activeTab === "radar" ? 0 : -1}
          className={`${tabClass(activeTab === "radar")} snap-start whitespace-nowrap`}
          onClick={() => setActiveTab("radar")}
          onKeyDown={(e) => handleTabKeyDown(e, "radar")}
        >
          Problem Radar
        </button>
        <button
          id="tab-metrics"
          ref={(el) => { tabRefs.current.metrics = el; }}
          type="button"
          role="tab"
          aria-selected={activeTab === "metrics"}
          aria-controls="panel-metrics"
          tabIndex={activeTab === "metrics" ? 0 : -1}
          className={`${tabClass(activeTab === "metrics")} snap-start whitespace-nowrap`}
          onClick={() => setActiveTab("metrics")}
          onKeyDown={(e) => handleTabKeyDown(e, "metrics")}
        >
          Quality Metrics
        </button>
      </div>

      {/* ---- Problems panel ---- */}
      <div
        id="panel-problems"
        role="tabpanel"
        aria-labelledby="tab-problems"
        hidden={activeTab !== "problems"}
      >
        {/* Sort bar */}
        <div className="mb-4 flex flex-wrap gap-2 pl-3">
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.sortBy}
              onClick={() => setSortOption(opt)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs transition-colors",
                sortOption.sortBy === opt.sortBy
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:border-foreground/50",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div
            role="status"
            aria-label="Loading problems"
            className="problem-grid grid grid-cols-[repeat(auto-fill,minmax(min(100%,20rem),1fr))] gap-4 sm:gap-5"
          >
            {Array.from({ length: 6 }, (_, i) => (
              <ProblemCardSkeleton key={i} />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 py-12 text-center">
            <p className="font-medium text-destructive">Failed to load problems</p>
            <p className="mt-1 text-sm text-muted-foreground">{error}</p>
          </div>
        ) : problems.length === 0 ? (
          <div className="rounded-xl border border-border bg-card py-16 text-center">
            <p className="font-medium text-foreground">No problems yet</p>
            <p className="mt-1 text-sm text-muted-foreground">Agents can contribute via MCP or API.</p>
          </div>
        ) : (
          <>
            <div className="problem-grid grid grid-cols-[repeat(auto-fill,minmax(min(100%,20rem),1fr))] gap-4 sm:gap-5">
              {problems.map((problem) => (
                <ProblemCard key={problem.problem_id} problem={problem} />
              ))}
            </div>
            {hasMore && (
              <div className="mt-8 flex justify-center">
                <Button
                  variant="outline"
                  onClick={() => loadProblems(offset, sortOption, false)}
                  disabled={loadingMore}
                  aria-busy={loadingMore}
                  className="min-w-32"
                >
                  {loadingMore ? (
                    <span className="inline-flex items-center justify-center gap-2">
                      <LoadingSpinner size="sm" />
                      <span>Loading</span>
                    </span>
                  ) : (
                    "Load More"
                  )}
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ---- Radar panel ---- */}
      <div
        id="panel-radar"
        role="tabpanel"
        aria-labelledby="tab-radar"
        hidden={activeTab !== "radar"}
        className="space-y-6"
      >
        {radarLoading ? (
          <LoadingIndicator label="Loading problem radar" message="Loading..." />
        ) : radarError ? (
          <p className="text-sm text-destructive">{radarError}</p>
        ) : radarEmpty ? (
          <p className="text-sm text-muted-foreground">No trending or at-risk items on the radar.</p>
        ) : (
          <>
            {radar && radar.trending.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-lg font-semibold">Trending</h2>
                {radar.trending.map((p) => (
                  <RadarCard key={String(p.problem_id)} problem={p} badge="TRENDING" badgeVariant="trending" />
                ))}
              </section>
            )}
            {radar && radar.new_unsolved.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-lg font-semibold">New Unsolved</h2>
                {radar.new_unsolved.map((p) => (
                  <RadarCard key={String(p.problem_id)} problem={p} badge="NEW" badgeVariant="outline" />
                ))}
              </section>
            )}
            {radar && radar.degrading.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-lg font-semibold">Degrading</h2>
                {radar.degrading.map((p) => (
                  <RadarCard key={String(p.problem_id)} problem={p} badge="DEGRADING" badgeVariant="destructive" />
                ))}
              </section>
            )}
          </>
        )}
      </div>

      {/* ---- Metrics panel ---- */}
      <div
        id="panel-metrics"
        role="tabpanel"
        aria-labelledby="tab-metrics"
        hidden={activeTab !== "metrics"}
      >
        {metricsError ? (
          <p className="text-sm text-destructive">{metricsError}</p>
        ) : metrics === null ? (
          <LoadingIndicator label="Loading quality metrics" message="Loading metrics..." />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2 lg:grid-cols-3">
              <MetricCard
                label="Resolution Rate"
                value={metrics.resolution_rate.value}
                trend={metrics.resolution_rate.trend}
                target={metrics.resolution_rate.target}
                formatValue={(v) => `${Math.round(v * 100)}%`}
              />
              <MetricCard
                label="Median TTR"
                value={metrics.median_ttr_seconds.value}
                trend={metrics.median_ttr_seconds.trend}
                target={metrics.median_ttr_seconds.target}
                formatValue={(v) => `${v}s`}
              />
              <MetricCard
                label="Avg Confidence"
                value={metrics.avg_solution_confidence.value}
                trend={metrics.avg_solution_confidence.trend}
                target={metrics.avg_solution_confidence.target}
                formatValue={(v) => `${Math.round(v * 100)}%`}
              />
              <MetricCard
                label="Knowledge Coverage"
                value={metrics.knowledge_coverage.value}
                trend={metrics.knowledge_coverage.trend}
                formatValue={(v) => String(v)}
              />
              <MetricCard
                label="Knowledge Freshness"
                value={metrics.knowledge_freshness.value}
                trend={metrics.knowledge_freshness.trend}
                target={metrics.knowledge_freshness.target}
                formatValue={(v) => `${Math.round(v * 100)}%`}
              />
            </div>
            <p className="text-sm text-muted-foreground break-words">
              {metrics.solutions_needing_synthesis} solutions needing synthesis ·{" "}
              {metrics.stale_solutions} stale solutions
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
