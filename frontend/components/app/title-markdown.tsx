"use client";

import { memo } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { sharedMarkdownCode } from "@/components/app/markdown-shared";

function buildTitleComponents(linkLike: Components["a"]): Components {
  return {
    p: ({ children }) => <span className="block">{children}</span>,
    h1: ({ children }) => (
      <span className="block font-semibold">{children}</span>
    ),
    h2: ({ children }) => (
      <span className="block font-semibold">{children}</span>
    ),
    h3: ({ children }) => (
      <span className="block font-semibold">{children}</span>
    ),
    strong: ({ children }) => (
      <strong className="font-semibold">{children}</strong>
    ),
    em: ({ children }) => <em className="italic">{children}</em>,
    ul: ({ children }) => (
      <div className="my-1">
        <ul className="list-disc space-y-0.5 pl-5">{children}</ul>
      </div>
    ),
    ol: ({ children }) => (
      <div className="my-1">
        <ol className="list-decimal space-y-0.5 pl-5">{children}</ol>
      </div>
    ),
    li: ({ children }) => <li className="leading-snug">{children}</li>,
    a: linkLike,
    code: sharedMarkdownCode,
    pre: ({ children }) => (
      <pre className="my-1 overflow-x-auto rounded-md border border-white/10 bg-black/40 p-2 font-mono text-xs leading-relaxed [&>code]:bg-transparent [&>code]:p-0 [&>code]:text-inherit">
        {children}
      </pre>
    ),
    blockquote: ({ children }) => (
      <div className="my-1 border-l-2 border-white/15 pl-3 text-muted-foreground italic">
        {children}
      </div>
    ),
    hr: () => <div className="my-2 h-px bg-white/10" />,
    table: ({ children }) => (
      <div className="my-1 overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-muted/40">{children}</thead>,
    th: ({ children }) => (
      <th className="border border-white/10 px-2 py-1 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="border border-white/10 px-2 py-1 align-top">{children}</td>
    ),
  };
}

const TITLE_COMPONENTS_LINK: Components = buildTitleComponents(
  ({ href, children }) => (
    <a
      href={href}
      className="font-medium text-coral underline-offset-2 hover:underline"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
);

const TITLE_COMPONENTS_INSIDE_LINK: Components = buildTitleComponents(
  ({ href, children }) => (
    <span className="text-coral underline decoration-coral/40" title={href}>
      {children}
    </span>
  ),
);

export const TitleMarkdown = memo(function TitleMarkdown({
  content,
  insideLink = false,
}: {
  content: string;
  /** When true, markdown links render as spans (avoids nested &lt;a&gt; inside Next &lt;Link&gt;). */
  insideLink?: boolean;
}) {
  return (
    <div className="title-markdown min-w-0 text-foreground [&_.font-mono]:font-mono">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={
          insideLink ? TITLE_COMPONENTS_INSIDE_LINK : TITLE_COMPONENTS_LINK
        }
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
