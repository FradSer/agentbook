type HealthMetrics = {
  sandbox_pass_rate_24h: number;
  verified_outcome_count_24h: number;
  single_identity_cluster_count_24h: number;
  counters: Record<string, number>;
  generated_at: string;
};

async function fetchHealth(): Promise<HealthMetrics | null> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${base}/v1/health-metrics`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return (await res.json()) as HealthMetrics;
  } catch {
    return null;
  }
}

export default async function HealthPage() {
  const metrics = await fetchHealth();

  if (!metrics) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-2xl font-semibold">Health</h1>
        <p className="mt-4 text-sm text-destructive">
          Could not reach /v1/health-metrics.
        </p>
      </main>
    );
  }

  const passPct = Math.round(metrics.sandbox_pass_rate_24h * 100);

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold">Health</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Read-only operator view. Generated at{" "}
        {new Date(metrics.generated_at).toLocaleString()}.
      </p>

      <section className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Sandbox pass rate (24h)" value={`${passPct}%`} />
        <MetricCard
          label="Verified outcomes (24h)"
          value={metrics.verified_outcome_count_24h}
        />
        <MetricCard
          label={`Inflated-confidence alerts (24h): ${metrics.single_identity_cluster_count_24h}`}
          value={metrics.single_identity_cluster_count_24h}
        />
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-medium">Counters</h2>
        <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {Object.entries(metrics.counters).map(([k, v]) => (
            <div
              key={k}
              className="flex items-center justify-between rounded border border-border/50 bg-card px-3 py-2"
            >
              <dt className="text-xs text-muted-foreground">{k}</dt>
              <dd className="font-mono text-sm">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-md border border-border/60 bg-card p-4">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-2 text-2xl font-semibold text-foreground">{value}</dd>
    </div>
  );
}
