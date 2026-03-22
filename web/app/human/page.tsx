"use client";

import { useEffect, useRef, useState } from "react";

import { LoadingIndicator } from "@/components/ui/loading-indicator";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchMetrics, fetchRadar, getProblems } from "@/lib/api";
import { focusRing } from "@/lib/focus-ring";
import { MetricsResponse, ProblemListItem, RadarProblem, RadarResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const TAB_ORDER = ["problems", "radar", "metrics"] as const;
type TabId = (typeof TAB_ORDER)[number];

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

function ProblemCard({
  problem,
  badge,
  badgeVariant = "secondary",
}: {
  problem: RadarProblem;
  badge: string;
  badgeVariant?: "secondary" | "destructive" | "outline";
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

export default function HumanPage() {
  const [activeTab, setActiveTab] = useState<TabId>("problems");
  const [problems, setProblems] = useState<ProblemListItem[]>([]);
  const [problemsLoading, setProblemsLoading] = useState(true);
  const [radar, setRadar] = useState<RadarResponse | null>(null);
  const [radarError, setRadarError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [radarLoading, setRadarLoading] = useState(true);
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});

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

  async function loadProblems() {
    try {
      const data = await getProblems({ limit: 50 });
      setProblems(data);
    } catch {
    } finally {
      setProblemsLoading(false);
    }
  }

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
    } catch {
    }
  }

  useEffect(() => {
    void loadProblems();
    void loadRadar();
    void loadMetrics();
    const id = setInterval(() => {
      void loadRadar();
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  const isEmpty =
    radar !== null &&
    radar.trending.length === 0 &&
    radar.new_unsolved.length === 0 &&
    radar.degrading.length === 0;

  const tabClass = (isActive: boolean) =>
    cn(
      focusRing,
      "shrink-0 min-h-11 touch-manipulation rounded-t-lg px-3 py-2 text-sm font-medium border-b-2 -mb-px",
      isActive ? "border-foreground text-foreground" : "border-transparent text-muted-foreground",
    );

  return (
    <div className="space-y-6">
      <h1
        id="human-dashboard-title"
        className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl"
      >
        Human dashboard
      </h1>
      <p id="human-tablist-hint" className="sr-only">
        When tabs do not all fit on screen, scroll horizontally to reach Problems, Problem Radar, and
        Quality Metrics.
      </p>
      <div>
        <div
          role="tablist"
          aria-labelledby="human-dashboard-title"
          aria-describedby="human-tablist-hint"
          aria-orientation="horizontal"
          className="-mx-1 mb-2 flex snap-x snap-mandatory gap-1 overflow-x-auto scroll-smooth border-b border-border pb-px [scrollbar-width:thin] sm:mx-0 sm:mb-4 sm:gap-2 [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/18 [&::-webkit-scrollbar-track]:bg-transparent"
        >
          <button
            id="human-tab-problems"
            ref={(el) => {
              tabRefs.current.problems = el;
            }}
            type="button"
            role="tab"
            aria-selected={activeTab === "problems"}
            aria-controls="human-panel-problems"
            tabIndex={activeTab === "problems" ? 0 : -1}
            className={`${tabClass(activeTab === "problems")} snap-start whitespace-nowrap`}
            onClick={() => setActiveTab("problems")}
            onKeyDown={(e) => handleTabKeyDown(e, "problems")}
          >
            Problems
          </button>
          <button
            id="human-tab-radar"
            ref={(el) => {
              tabRefs.current.radar = el;
            }}
            type="button"
            role="tab"
            aria-selected={activeTab === "radar"}
            aria-controls="human-panel-radar"
            tabIndex={activeTab === "radar" ? 0 : -1}
            className={`${tabClass(activeTab === "radar")} snap-start whitespace-nowrap`}
            onClick={() => setActiveTab("radar")}
            onKeyDown={(e) => handleTabKeyDown(e, "radar")}
          >
            Problem Radar
          </button>
          <button
            id="human-tab-metrics"
            ref={(el) => {
              tabRefs.current.metrics = el;
            }}
            type="button"
            role="tab"
            aria-selected={activeTab === "metrics"}
            aria-controls="human-panel-metrics"
            tabIndex={activeTab === "metrics" ? 0 : -1}
            className={`${tabClass(activeTab === "metrics")} snap-start whitespace-nowrap`}
            onClick={() => setActiveTab("metrics")}
            onKeyDown={(e) => handleTabKeyDown(e, "metrics")}
          >
            Quality Metrics
          </button>
        </div>


        <div
          id="human-panel-problems"
          role="tabpanel"
          aria-labelledby="human-tab-problems"
          hidden={activeTab !== "problems"}
        >
          {problemsLoading ? (
            <LoadingIndicator label="Loading problems" message="Loading…" />
          ) : problems.length === 0 ? (
            <p className="text-sm text-muted-foreground">No problems yet.</p>
          ) : (
            <div className="human-problem-list space-y-3">
              {problems.map((p) => (
                <Card key={p.problem_id}>
                  <CardContent className="pt-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                      <p className="min-w-0 flex-1 text-sm font-medium break-words">{p.description}</p>
                      <Badge variant="secondary" className="w-fit shrink-0 self-start sm:self-auto">
                        {Math.round(p.best_confidence * 100)}%
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        <div
          id="human-panel-radar"
          role="tabpanel"
          aria-labelledby="human-tab-radar"
          hidden={activeTab !== "radar"}
          className="space-y-6"
        >
          {radarLoading ? (
            <LoadingIndicator label="Loading problem radar" message="Loading…" />
          ) : radarError ? (
            <p className="text-sm text-destructive">{radarError}</p>
          ) : isEmpty ? (
            <p className="text-sm text-muted-foreground">No trending or at-risk items on the radar.</p>
          ) : (
            <>
              {radar && radar.trending.length > 0 && (
                <section className="space-y-3">
                  <h2 className="text-lg font-semibold">Trending</h2>
                  {radar.trending.map((p) => (
                    <ProblemCard key={String(p.problem_id)} problem={p} badge="TRENDING" />
                  ))}
                </section>
              )}
              {radar && radar.new_unsolved.length > 0 && (
                <section className="space-y-3">
                  <h2 className="text-lg font-semibold">New Unsolved</h2>
                  {radar.new_unsolved.map((p) => (
                    <ProblemCard
                      key={String(p.problem_id)}
                      problem={p}
                      badge="NEW"
                      badgeVariant="outline"
                    />
                  ))}
                </section>
              )}
              {radar && radar.degrading.length > 0 && (
                <section className="space-y-3">
                  <h2 className="text-lg font-semibold">Degrading</h2>
                  {radar.degrading.map((p) => (
                    <ProblemCard
                      key={String(p.problem_id)}
                      problem={p}
                      badge="DEGRADING"
                      badgeVariant="destructive"
                    />
                  ))}
                </section>
              )}
            </>
          )}
        </div>

        <div
          id="human-panel-metrics"
          role="tabpanel"
          aria-labelledby="human-tab-metrics"
          hidden={activeTab !== "metrics"}
        >
          {metrics === null ? (
            <LoadingIndicator label="Loading quality metrics" message="Loading metrics…" />
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
    </div>
  );
}
