import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground shadow-sm hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80",
        outline: "text-foreground border-border",
        high: "bg-[var(--tier-high-bg)] text-[var(--tier-high-fg)] border-[var(--tier-high-border)]",
        med: "bg-[var(--tier-med-bg)] text-[var(--tier-med-fg)] border-[var(--tier-med-border)]",
        low: "border-dashed border-border bg-transparent text-muted-foreground",
        canonical:
          "bg-[var(--canonical-bg)] text-[var(--canonical-fg)] border-[var(--canonical-border)]",
        trending:
          "bg-[var(--trending-bg)] text-[var(--trending-fg)] border-[var(--trending-border)]",
        "tag-default":
          "bg-[var(--tag-default-bg)] text-[var(--tag-default-fg)] border-[var(--tag-default-border)]",
        "tag-green":
          "bg-[var(--tag-green-bg)] text-[var(--tag-green-fg)] border-[var(--tag-green-border)]",
        "tag-blue":
          "bg-[var(--tag-blue-bg)] text-[var(--tag-blue-fg)] border-[var(--tag-blue-border)]",
        "tag-purple":
          "bg-[var(--tag-purple-bg)] text-[var(--tag-purple-fg)] border-[var(--tag-purple-border)]",
        "tag-amber":
          "bg-[var(--tag-amber-bg)] text-[var(--tag-amber-fg)] border-[var(--tag-amber-border)]",
        "tag-coral":
          "bg-[var(--tag-coral-bg)] text-[var(--tag-coral-fg)] border-[var(--tag-coral-border)]",
        researching:
          "bg-[var(--research-bg)] text-[var(--research-fg)] border-[var(--research-border)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
