import { cn } from "@/lib/utils";

const spinnerSize = {
  sm: "size-3.5 border-[1.5px]",
  md: "size-5 border-2",
  lg: "size-7 border-2",
} as const;

export type LoadingSpinnerSize = keyof typeof spinnerSize;

/** GPU-friendly ring; rotation is linear by nature. Reduced motion: static ring, no spin. */
export function LoadingSpinner({
  size = "md",
  className,
}: {
  size?: LoadingSpinnerSize;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-block shrink-0 rounded-full border-white/12 border-t-primary",
        "animate-spin motion-reduce:animate-none motion-reduce:border-t-muted-foreground/45 motion-reduce:opacity-70",
        spinnerSize[size],
        className,
      )}
      aria-hidden
    />
  );
}

export type LoadingIndicatorProps = {
  /** Announced to screen readers */
  label: string;
  /** Visible caption; omit for spinner-only (label still read by SR) */
  message?: string;
  size?: LoadingSpinnerSize;
  variant?: "inline" | "centered" | "block";
  className?: string;
};

/**
 * Unified loading presentation: coral accent ring + optional caption.
 */
export function LoadingIndicator({
  label,
  message,
  size = "md",
  variant = "inline",
  className,
}: LoadingIndicatorProps) {
  const statusProps = {
    role: "status" as const,
    ...(message ? {} : { "aria-label": label }),
  };

  const body = (
    <>
      <LoadingSpinner size={size} />
      {message ? (
        <span className="text-sm text-muted-foreground">{message}</span>
      ) : null}
    </>
  );

  if (variant === "centered") {
    return (
      <div
        {...statusProps}
        className={cn(
          "flex flex-col items-center justify-center gap-3 py-16 text-center",
          "animate-in fade-in slide-in-from-bottom-2 duration-500 ease-out",
          className,
        )}
      >
        {body}
      </div>
    );
  }

  if (variant === "block") {
    return (
      <div
        {...statusProps}
        className={cn(
          "py-8 animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out",
          className,
        )}
      >
        <div className="flex flex-col items-start gap-3">{body}</div>
      </div>
    );
  }

  return (
    <div
      {...statusProps}
      className={cn(
        "inline-flex items-center gap-2 animate-in fade-in duration-200",
        className,
      )}
    >
      {body}
    </div>
  );
}
