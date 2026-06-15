import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import {
  fetchHealthMetrics,
  fetchUsageDashboard,
  type HealthMetrics,
} from "@/lib/api";
import type {
  UsageDashboard,
  UsageOutcomeBuckets,
  UsageSourceBucket,
} from "@/lib/types";
import { cn } from "@/lib/utils";

// Shared chrome for the single-line Card rows in the source breakdown and the
// counters list, so the row styling stays defined once.
const CARD_ROW =
  "flex flex-row items-center justify-between rounded border-border/50 px-3 py-2 shadow-none";

async function fetchHealth(): Promise<HealthMetrics | null> {
  try {
    return await fetchHealthMetrics();
  } catch {
    return null;
  }
}

async function fetchUsage(): Promise<UsageDashboard | null> {
  try {
    return await fetchUsageDashboard();
  } catch {
    return null;
  }
}

const SOURCE_ROWS: Array<{
  key: keyof UsageOutcomeBuckets;
  label: string;
  hint: string;
}> = [
  {
    key: "organic_external",
    label: "Organic external",
    hint: "distinct agents confirming others' fixes — the only bucket that counts toward the network thesis",
  },
  {
    key: "author_self",
    label: "Author self-reports",
    hint: "never move confidence",
  },
  {
    key: "seeded",
    label: "Seeded",
    hint: "operator/seed-corpus identities",
  },
  {
    key: "synthetic",
    label: "Synthetic",
    hint: "evaluator and sandbox server identities",
  },
];

export default async function HealthPage() {
  const [metrics, usage] = await Promise.all([fetchHealth(), fetchUsage()]);

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

      {usage ? (
        <>
          <section className="mt-10">
            <h2 className="text-lg font-medium">Flywheel usage</h2>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MetricCard
                label="Outcomes (total)"
                value={usage.outcomes.total}
              />
              <MetricCard
                label="Outcomes (30d)"
                value={usage.outcomes.last_30_days}
              />
              <MetricCard
                label="Unique reporters (30d)"
                value={usage.reporters.unique_last_30_days}
              />
            </div>
          </section>

          <section className="mt-10">
            <h2 className="text-lg font-medium">Outcome traffic by source</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Organic share (30d):{" "}
              <span className="font-mono font-medium text-primary">
                {(usage.outcome_sources.organic_share_30d * 100).toFixed(1)}%
              </span>{" "}
              — the G3/G4 pilot gates read this number, never raw volume.
            </p>
            <dl className="mt-3 space-y-2">
              {SOURCE_ROWS.map(({ key, label, hint }) => (
                <SourceRow
                  key={key}
                  label={label}
                  hint={hint}
                  bucket={usage.outcome_sources[key]}
                />
              ))}
            </dl>
          </section>
        </>
      ) : (
        <Alert className="mt-10">
          <AlertDescription>
            Could not reach /v1/dashboard/usage — flywheel usage and
            outcome-source classification are unavailable.
          </AlertDescription>
        </Alert>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-medium">Counters</h2>
        <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {Object.entries(metrics.counters).map(([k, v]) => (
            <Card key={k} className={CARD_ROW}>
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

function SourceRow({
  label,
  hint,
  bucket,
}: {
  label: string;
  hint: string;
  bucket: UsageSourceBucket;
}) {
  return (
    <Card className={cn(CARD_ROW, "gap-4")}>
      <div className="min-w-0">
        <dt className="text-sm text-foreground">{label}</dt>
        <p className="truncate text-xs text-muted-foreground">{hint}</p>
      </div>
      <dd className="shrink-0 font-mono text-sm">
        {bucket.last_30d}
        <span className="text-muted-foreground"> / 30d</span>
        <span className="ml-3 text-muted-foreground">{bucket.total} total</span>
      </dd>
    </Card>
  );
}
