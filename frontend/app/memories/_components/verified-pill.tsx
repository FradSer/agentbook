import { cn } from "@/lib/utils";

type VerifiedPillProps = {
  size?: "sm" | "md";
};

export function VerifiedPill({ size = "sm" }: VerifiedPillProps) {
  return (
    <span
      role="img"
      aria-label="sandbox verified"
      className={cn(
        "inline-flex items-center rounded-full bg-accent/80 px-2 py-0.5",
        "text-[0.7rem] font-medium uppercase tracking-wide text-accent-foreground",
        size === "md" && "px-3 py-1 text-xs",
      )}
    >
      Verified
    </span>
  );
}
