"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { sharedMarkdownCode, sharedMarkdownPre } from "@/components/app/markdown-shared";
import { cn } from "@/lib/utils";

const markdownComponents: Components = {
  p: ({ children }) => (
    <p className="mb-3 text-base leading-relaxed last:mb-0">{children}</p>
  ),
  h1: ({ children }) => (
    <h2 className="mb-2 mt-6 text-lg font-semibold tracking-tight first:mt-0">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="mb-2 mt-6 text-base font-semibold tracking-tight first:mt-0">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="mb-2 mt-4 text-sm font-semibold first:mt-0">{children}</h4>
  ),
  ul: ({ children }) => (
    <ul className="my-3 list-disc space-y-1 pl-6 text-base leading-relaxed">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-3 list-decimal space-y-1 pl-6 text-base leading-relaxed">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-white/15 pl-4 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="font-medium text-coral underline-offset-2 hover:underline"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-6 border-white/10" />,
  pre: sharedMarkdownPre,
  code: sharedMarkdownCode,
  table: ({ children }) => (
    <div className="my-4 w-full min-w-0 overflow-x-auto rounded-lg border border-white/10">
      <table className="w-full min-w-[20rem] border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-white/[0.04]">{children}</thead>,
  th: ({ children }) => (
    <th className="border border-white/10 px-3 py-2 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border border-white/10 px-3 py-2 align-top">{children}</td>
  ),
};

export function SolutionMarkdown({ content, className }: { content: string; className?: string }) {
  return (
    <div
      className={cn(
        "solution-markdown w-full min-w-0 max-w-full text-foreground",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
