"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge } from "@/components/ui/badge";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Skeleton } from "@/components/ui/skeleton";
import { searchProblems } from "@/lib/api";
import { focusRing } from "@/lib/focus-ring";
import type { SearchResult } from "@/lib/types";
import { getRecent, pushRecent } from "@/lib/use-recent-queries";
import { cn, getConfidenceTier } from "@/lib/utils";

const DEBOUNCE_MS = 180;
const MAX_RESULTS = 8;
const HIGH_CONFIDENCE_THRESHOLD = 0.7;

const EXAMPLE_QUERIES = [
  "Railway deployment failure",
  "pgvector extension missing",
  "OpenRouter rate limit",
];

const tierLabel: Record<"high" | "med" | "low", string> = {
  high: "high confidence",
  med: "medium confidence",
  low: "low confidence",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-white/[0.06] px-1 py-px font-mono text-[10px] leading-tight text-muted-foreground/70">
      {children}
    </kbd>
  );
}

function GroupHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-4 pt-2 pb-0.5 text-[10px] font-medium tracking-widest text-muted-foreground/60 uppercase select-none">
      {children}
    </div>
  );
}

function SkeletonRows() {
  return (
    <div className="flex flex-col gap-px py-1">
      {[72, 88, 60].map((w, i) => (
        <div key={w} className="flex items-start gap-3 px-4 py-2">
          <div className="min-w-0 flex-1 flex flex-col gap-1.5">
            <Skeleton className="h-3.5 rounded" style={{ width: `${w}%` }} />
            <Skeleton
              className="h-2.5 rounded"
              style={{ width: `${[44, 56, 38][i]}%` }}
            />
          </div>
          <Skeleton className="h-5 w-9 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  query,
  onSelectExample,
}: {
  query: string;
  onSelectExample: (q: string) => void;
}) {
  return (
    <div className="px-4 py-4 text-center">
      <p className="text-sm text-muted-foreground">
        No results for{" "}
        <span className="font-medium text-foreground/70">
          &ldquo;{query}&rdquo;
        </span>
      </p>
      <p className="mt-0.5 text-[11px] text-muted-foreground/50">
        Try different keywords or a broader phrase.
      </p>
      <div className="mt-2 flex flex-wrap justify-center gap-1.5">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSelectExample(q)}
            className={cn(
              "rounded px-2 py-0.5 text-[11px] text-coral-light border border-border bg-transparent hover:bg-white/[0.04] transition-colors",
              focusRing,
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="px-4 py-3">
      <p className="text-sm text-destructive">Search unavailable</p>
      <p className="mt-0.5 text-[11px] text-muted-foreground/60">{message}</p>
    </div>
  );
}

function DefaultState({
  recent,
  onSelectRecent,
}: {
  recent: string[];
  onSelectRecent: (q: string) => void;
}) {
  const items = recent.length > 0 ? recent : EXAMPLE_QUERIES;
  const heading = recent.length > 0 ? "RECENT" : "TRY";

  return (
    <>
      <GroupHeading>{heading}</GroupHeading>
      <div className="flex flex-col pb-0.5">
        {items.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSelectRecent(q)}
            className={cn(
              "px-4 py-1.5 text-left text-sm text-muted-foreground hover:bg-white/[0.04] hover:text-foreground transition-colors rounded",
              focusRing,
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </>
  );
}

// ─── Highlight helpers (verbatim from original search-box.tsx) ────────────────

function getHighlightSegments(
  text: string,
  query: string,
): { text: string; highlight: boolean }[] {
  if (!query) return [{ text, highlight: false }];
  try {
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(escaped, "gi");
    const segments: { text: string; highlight: boolean }[] = [];
    let last = 0;
    let match: RegExpExecArray | null;
    // biome-ignore lint/suspicious/noAssignInExpressions: standard regex loop pattern
    while ((match = regex.exec(text)) !== null) {
      if (match.index > last) {
        segments.push({
          text: text.slice(last, match.index),
          highlight: false,
        });
      }
      segments.push({ text: match[0], highlight: true });
      last = match.index + match[0].length;
    }
    if (last < text.length) {
      segments.push({ text: text.slice(last), highlight: false });
    }
    return segments.length > 0 ? segments : [{ text, highlight: false }];
  } catch {
    return [{ text, highlight: false }];
  }
}

function HighlightedText({
  text,
  query,
  className,
}: {
  text: string;
  query: string;
  className?: string;
}) {
  const segments = getHighlightSegments(text, query);
  return (
    <span className={className}>
      {segments.map((seg, i) =>
        seg.highlight ? (
          <mark
            key={`${i}-${seg.text}`}
            className="bg-transparent font-medium text-coral-light"
          >
            {seg.text}
          </mark>
        ) : (
          <span key={`${i}-${seg.text}`}>{seg.text}</span>
        ),
      )}
    </span>
  );
}

// ─── Result row ───────────────────────────────────────────────────────────────

function ResultRow({
  id,
  result,
  query,
  active,
  onMouseEnter,
  onSelect,
}: {
  id: string;
  result: SearchResult;
  query: string;
  active: boolean;
  onMouseEnter: () => void;
  onSelect: () => void;
}) {
  const tier = result.best_solution
    ? getConfidenceTier(result.best_solution.confidence)
    : null;
  const confidencePct = result.best_solution
    ? Math.round(result.best_solution.confidence * 100)
    : null;
  const plainTitle = result.description_preview.replace(/[*_`~#[\]()]/g, "");

  return (
    <Link
      id={id}
      role="option"
      aria-selected={active}
      tabIndex={-1}
      href={`/memories/${result.problem_id}`}
      onClick={(e) => {
        e.preventDefault();
        onSelect();
      }}
      onMouseEnter={onMouseEnter}
      className="flex w-full items-start gap-3 px-4 py-2 text-sm"
    >
      <div className="min-w-0 flex-1">
        <p className="leading-snug text-foreground">
          {query &&
          !result.description_preview.includes("*") &&
          !result.description_preview.includes("`") ? (
            <HighlightedText text={plainTitle} query={query} />
          ) : (
            <TitleMarkdown content={result.description_preview} insideLink />
          )}
        </p>
        {result.tags.length > 0 && (
          <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
            <HighlightedText
              text={result.tags.slice(0, 3).join(" · ")}
              query={query}
            />
          </p>
        )}
      </div>
      {tier && confidencePct !== null ? (
        <Badge
          variant={tier}
          aria-label={`Best solution ${tierLabel[tier]} (${confidencePct} percent)`}
        >
          {confidencePct}%
        </Badge>
      ) : (
        <Badge variant="low">new</Badge>
      )}
    </Link>
  );
}

// ─── Results (grouped by confidence) ─────────────────────────────────────────

function GroupedResults({
  results,
  query,
  activeIndex,
  listboxId,
  onMouseEnter,
  onSelect,
}: {
  results: SearchResult[];
  query: string;
  activeIndex: number;
  listboxId: string;
  onMouseEnter: (i: number) => void;
  onSelect: (r: SearchResult) => void;
}) {
  const high = results.filter(
    (r) => (r.best_solution?.confidence ?? 0) >= HIGH_CONFIDENCE_THRESHOLD,
  );
  const lower = results.filter(
    (r) => (r.best_solution?.confidence ?? 0) < HIGH_CONFIDENCE_THRESHOLD,
  );

  let globalIndex = 0;

  function renderRow(result: SearchResult, index: number) {
    const gi = index;
    return (
      <CommandItem
        key={result.problem_id}
        value={result.problem_id}
        onSelect={() => onSelect(result)}
        className="p-0 data-[selected=true]:bg-secondary data-[selected=true]:text-foreground"
      >
        <ResultRow
          id={`${listboxId}-option-${gi}`}
          result={result}
          query={query}
          active={gi === activeIndex}
          onMouseEnter={() => onMouseEnter(gi)}
          onSelect={() => onSelect(result)}
        />
      </CommandItem>
    );
  }

  return (
    <>
      {high.length > 0 && (
        <CommandGroup className="p-0">
          <GroupHeading>HIGH CONFIDENCE · {high.length}</GroupHeading>
          {high.map((r) => {
            const el = renderRow(r, globalIndex);
            globalIndex++;
            return el;
          })}
        </CommandGroup>
      )}
      {lower.length > 0 && (
        <CommandGroup className={high.length > 0 ? "mt-2 p-0" : "p-0"}>
          <GroupHeading>
            {high.length > 0 ? "LOWER CONFIDENCE" : "RESULTS"} · {lower.length}
          </GroupHeading>
          {lower.map((r) => {
            const el = renderRow(r, globalIndex);
            globalIndex++;
            return el;
          })}
        </CommandGroup>
      )}
      <div className="flex items-center gap-2 border-t border-border px-4 py-1 text-[11px] text-muted-foreground/50">
        <span className="flex items-center gap-1">
          <Kbd>↑</Kbd>
          <Kbd>↓</Kbd>
          navigate
        </span>
        <span className="flex items-center gap-1">
          <Kbd>↵</Kbd>
          open
        </span>
        <span className="flex items-center gap-1">
          <Kbd>Esc</Kbd>
          close
        </span>
      </div>
    </>
  );
}

// ─── Main SearchDialog ────────────────────────────────────────────────────────

export function SearchDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recent, setRecent] = useState<string[]>([]);
  const isComposingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const liveRegionId = useId();

  // Load recent on open
  useEffect(() => {
    if (open) {
      setRecent(getRecent());
    }
  }, [open]);

  // Reset state on close
  useEffect(() => {
    if (!open) {
      setValue("");
      setResults([]);
      setLoading(false);
      setError(null);
      setActiveIndex(-1);
    }
  }, [open]);

  // Debounced search
  useEffect(() => {
    const trimmed = value.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }
    setResults([]);
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchProblems(trimmed, { limit: MAX_RESULTS, signal: controller.signal })
        .then((data) => {
          setResults(data.results);
          setError(null);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setResults([]);
          setError(err instanceof Error ? err.message : "Search failed");
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [value]);

  // Reset active index on query change
  useEffect(() => {
    setActiveIndex(-1);
  }, [value]);

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex < 0 || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(
      `[id="${listboxId}-option-${activeIndex}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, listboxId]);

  const totalResults = results.length;

  function selectResult(result: SearchResult) {
    pushRecent(value.trim());
    onOpenChange(false);
    router.push(`/memories/${result.problem_id}`);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (isComposingRef.current) return;
    if (e.key === "Escape") {
      if (value) {
        setValue("");
      } else {
        onOpenChange(false);
      }
      return;
    }
    if (totalResults === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % totalResults);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? totalResults - 1 : i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target =
        activeIndex >= 0 && activeIndex < totalResults
          ? results[activeIndex]
          : totalResults === 1
            ? results[0]
            : null;
      if (target) selectResult(target);
    }
  }

  function fillQuery(q: string) {
    setValue(q);
    inputRef.current?.focus();
  }

  const query = value.trim();
  const showResults = !loading && error === null && results.length > 0;
  const showEmpty =
    !loading && error === null && results.length === 0 && query.length > 0;
  const showDefault = !loading && error === null && query.length === 0;

  const liveMessage = loading
    ? "Searching…"
    : error
      ? `Search error: ${error}`
      : results.length > 0
        ? `${results.length} result${results.length === 1 ? "" : "s"} found`
        : query.length > 0
          ? "No results found"
          : "";

  return (
    <>
      {/* ARIA live region — outside Dialog so it's always in DOM */}
      <div
        id={liveRegionId}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {open ? liveMessage : ""}
      </div>

      <CommandDialog
        open={open}
        onOpenChange={onOpenChange}
        contentClassName="max-w-xl"
      >
        {/* Custom input — keeps IME, debounce, ARIA combobox intact */}
        <div className="flex items-center border-b border-border px-4">
          <input
            ref={inputRef}
            type="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="Search memories…"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => {
              isComposingRef.current = true;
            }}
            onCompositionEnd={() => {
              isComposingRef.current = false;
            }}
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={
              activeIndex >= 0
                ? `${listboxId}-option-${activeIndex}`
                : undefined
            }
            className="h-11 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          {value && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setValue("")}
              className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground",
                focusRing,
              )}
            >
              <svg
                aria-hidden="true"
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              >
                <path d="M1 1l10 10M11 1L1 11" />
              </svg>
            </button>
          )}
        </div>

        <CommandList
          id={listboxId}
          ref={listRef}
          role="listbox"
          aria-label="Search results"
          className="max-h-[min(70vh,26rem)] overflow-y-auto py-1"
        >
          {loading && <SkeletonRows />}

          {error !== null && !loading && (
            <CommandEmpty className="p-0">
              <ErrorState message={error} />
            </CommandEmpty>
          )}

          {showDefault && (
            <DefaultState recent={recent} onSelectRecent={fillQuery} />
          )}

          {showEmpty && (
            <CommandEmpty className="p-0">
              <EmptyState query={query} onSelectExample={fillQuery} />
            </CommandEmpty>
          )}

          {showResults && (
            <GroupedResults
              results={results}
              query={query}
              activeIndex={activeIndex}
              listboxId={listboxId}
              onMouseEnter={setActiveIndex}
              onSelect={selectResult}
            />
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
