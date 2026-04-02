import * as React from "react";

import { cn } from "@/lib/utils";

/** Single source of truth: brand mark and agent avatars use the same tile shape. */
export const GRADIENT_COLOR_BLOCK_CLASS = "size-7 rounded-lg flex-shrink-0";

type GradientColorBlockProps = {
  background: string;
  className?: string;
} & React.ComponentPropsWithoutRef<"div">;

export const GradientColorBlock = React.memo(function GradientColorBlock({
  background,
  className,
  ...props
}: GradientColorBlockProps) {
  return (
    <div
      className={cn(GRADIENT_COLOR_BLOCK_CLASS, className)}
      style={{ background }}
      {...props}
    />
  );
});
