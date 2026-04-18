type DualScoreProps = {
  global: number;
  perEnvironment?: Record<string, number> | null;
};

export function DualScore({ global, perEnvironment }: DualScoreProps) {
  const topEnv =
    perEnvironment && Object.keys(perEnvironment).length > 0
      ? Object.entries(perEnvironment).reduce((best, entry) =>
          entry[1] > best[1] ? entry : best,
        )
      : null;

  return (
    <dl className="flex gap-6 text-sm">
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          Global
        </dt>
        <dd className="text-lg font-medium text-foreground">
          {global.toFixed(2)}
        </dd>
      </div>
      {topEnv ? (
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {topEnv[0]}
          </dt>
          <dd className="text-lg font-medium text-foreground">
            {topEnv[1].toFixed(2)}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}
