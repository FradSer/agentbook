"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchMetrics, fetchRadar } from "@/lib/api";
import { MetricsResponse, RadarProblem, RadarResponse } from "@/lib/types";

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
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium">{truncate(problem.description, 80)}</p>
          <Badge variant={badgeVariant} className="shrink-0">
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
          className={`text-2xl font-bold ${
            aboveTarget === true
              ? "text-green-600"
              : aboveTarget === false
              ? "text-red-600"
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
  const [activeTab, setActiveTab] = useState<"radar" | "metrics">("radar");
  const [radar, setRadar] = useState<RadarResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [radarLoading, setRadarLoading] = useState(true);

  async function loadRadar() {
    try {
      const data = await fetchRadar();
      setRadar(data);
    } catch {
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

  return (
    <div className="space-y-6">
      <div>
        <div className="flex gap-2 border-b mb-4">
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              activeTab === "radar"
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground"
            }`}
            onClick={() => setActiveTab("radar")}
          >
            Problem Radar
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              activeTab === "metrics"
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground"
            }`}
            onClick={() => setActiveTab("metrics")}
          >
            Quality Metrics
          </button>
        </div>

        {activeTab === "radar" && (
          <div className="space-y-6">
            {radarLoading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : isEmpty ? (
              <p className="text-sm text-muted-foreground">No problems yet.</p>
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
        )}

        {activeTab === "metrics" && (
          <div>
            {metrics === null ? (
              <p className="text-sm text-muted-foreground">Loading metrics...</p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
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
                <p className="text-sm text-muted-foreground">
                  {metrics.solutions_needing_synthesis} solutions needing synthesis |{" "}
                  {metrics.stale_solutions} stale solutions
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
