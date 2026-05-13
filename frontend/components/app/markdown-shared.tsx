import type { Components } from "react-markdown";

import { cn } from "@/lib/utils";

/** Inline + fenced `code`; uses `font-mono` (IBM Plex Mono from theme). */
export const sharedMarkdownCode: NonNullable<Components["code"]> = ({
  className,
  children,
  ...props
}) => {
  const isBlock = /language-[\w-]+/.test(className ?? "");
  if (isBlock) {
    return (
      <code className={cn(className, "font-mono text-sm")} {...props}>
        {children}
      </code>
    );
  }
  return (
    <code
      className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[0.9em] text-foreground"
      {...props}
    >
      {children}
    </code>
  );
};

export const sharedMarkdownPre: NonNullable<Components["pre"]> = ({
  children,
}) => (
  <pre className="mb-4 w-full min-w-0 overflow-x-auto rounded-lg border border-white/10 bg-black/45 p-4 font-mono text-sm leading-relaxed shadow-inner [&>code]:bg-transparent [&>code]:p-0 [&>code]:text-inherit">
    {children}
  </pre>
);
