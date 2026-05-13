import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { fetchHealthMetrics, type HealthMetrics } from "@/lib/api";

async function fetchHealth(): Promise<HealthMetrics | null> {
  try {
    return await fetchHealthMetrics();
  } catch {
    return null;
  }
}

export default async function HealthPage() {
  const metrics = await fetchHealth();

  if (!metrics) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-2xl font-semibold">Health</h1>
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>
            Could not reach /v1/health-metrics.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const passPct = Math.round(metrics.sandbox_pass_rate_24h * 100);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
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
          label="Inflated-confidence alerts (24h)"
          value={metrics.single_identity_cluster_count_24h}
        />
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-medium">Counters</h2>
        <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {Object.entries(metrics.counters).map(([k, v]) => (
            <Card
              key={k}
              className="flex flex-row items-center justify-between rounded border-border/50 px-3 py-2 shadow-none"
            >
              <dt className="text-xs text-muted-foreground">{k}</dt>
              <dd className="font-mono text-sm">{v}</dd>
            </Card>
          ))}
        </dl>
      </section>
    </div>
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
    <Card className="rounded-md border-border/60 p-4 shadow-none">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-2 text-2xl font-semibold text-foreground">{value}</dd>
    </Card>
  );
}
