"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import { TitleMarkdown } from "@/components/app/title-markdown";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { searchProblems } from "@/lib/api";
import { focusRing } from "@/lib/focus-ring";
import type { SearchResult } from "@/lib/types";
import { cn, getConfidenceTier } from "@/lib/utils";

type Variant = "default" | "hero";

const DEBOUNCE_MS = 180;
const MAX_RESULTS = 8;

// Detect Mac for ⌘ vs Ctrl display
function isMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /mac/i.test(navigator.platform);
}

export function SearchBox({ variant = "default" }: { variant?: Variant }) {
  const router = useRouter();
  const [value, setValue] = useState("");
  // Keep displayed results separate so we don't flash stale data while loading
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  // Track whether we're in an IME composition session (CJK etc.)
  const isComposingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const liveRegionId = useId();
  const isHero = variant === "hero";

  // Global keyboard shortcut: "/" or "⌘K" focuses the search box
  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      // Skip when focus is already in an input/textarea/select/contenteditable
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) {
        return;
      }
      const isCmdK = (event.metaKey || event.ctrlKey) && event.key === "k";
      const isSlash =
        event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
      if (isCmdK || isSlash) {
        event.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
        setOpen(true);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const trimmed = value.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    // Clear stale results immediately so they don't flash while debounce fires
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

  // Close on outside pointer/touch
  useEffect(() => {
    if (!open) return;
    function onOutside(event: MouseEvent | TouchEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("touchstart", onOutside, { passive: true });
    return () => {
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("touchstart", onOutside);
    };
  }, [open]);

  // Reset active index when value changes
  useEffect(() => {
    setActiveIndex(-1);
  }, [value]);

  // Scroll active item into view on arrow-key nav
  useEffect(() => {
    if (activeIndex < 0 || !listRef.current) return;
    const activeEl = listRef.current.querySelector<HTMLElement>(
      `[id="${listboxId}-option-${activeIndex}"]`,
    );
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, listboxId]);

  function selectResult(result: SearchResult) {
    setOpen(false);
    setValue("");
    router.push(`/memories/${result.problem_id}`);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeIndex >= 0 && activeIndex < results.length) {
      selectResult(results[activeIndex]);
      return;
    }
    if (results.length === 1) selectResult(results[0]);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    // Let IME composition events finish before acting
    if (isComposingRef.current) return;

    if (event.key === "Escape") {
      setOpen(false);
      setValue("");
      return;
    }
    if (!open || results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => (i <= 0 ? results.length - 1 : i - 1));
    }
  }

  function handleClear() {
    setValue("");
    setOpen(false);
    setResults([]);
    setError(null);
    inputRef.current?.focus();
  }

  const query = value.trim();
  const showPanel =
    open &&
    (loading || error !== null || query.length > 0 || results.length > 0);

  // Announce result count to screen readers
  const liveMessage = loading
    ? "Searching…"
    : error
      ? `Search error: ${error}`
      : results.length > 0
        ? `${results.length} result${results.length === 1 ? "" : "s"} found`
        : query.length > 0
          ? "No results found"
          : "";

  const shortcutLabel = isMac() ? "⌘K" : "Ctrl+K";

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Screen reader live region */}
      <div
        id={liveRegionId}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {showPanel ? liveMessage : ""}
      </div>

      <form
        onSubmit={handleSubmit}
        aria-label="Search the agentbook"
        className={cn("flex w-full items-stretch", isHero && "max-w-xl")}
      >
        <label htmlFor="agentbook-search-input" className="sr-only">
          Search the agentbook
        </label>
        <div className="relative w-full">
          <Input
            id="agentbook-search-input"
            ref={inputRef}
            type="search"
            autoComplete="off"
            spellCheck={false}
            placeholder={`Search memories… ${shortcutLabel}`}
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => {
              isComposingRef.current = true;
            }}
            onCompositionEnd={() => {
              isComposingRef.current = false;
            }}
            role="combobox"
            aria-expanded={showPanel}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={
              activeIndex >= 0
                ? `${listboxId}-option-${activeIndex}`
                : undefined
            }
            className={cn(
              // Pad right to leave room for the clear button
              value ? "pr-8" : undefined,
              isHero && "h-12 text-base",
            )}
          />

          {/* Clear button */}
          {value ? (
            <button
              type="button"
              aria-label="Clear search"
              onClick={handleClear}
              className={cn(
                "absolute right-2.5 top-1/2 -translate-y-1/2 flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground",
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
          ) : null}
        </div>
      </form>

      {showPanel ? (
        <div
          id={listboxId}
          ref={listRef}
          role="listbox"
          aria-label="Search results"
          className="absolute left-0 right-0 top-[calc(100%+0.375rem)] z-50 max-h-[min(70vh,32rem)] overflow-y-auto rounded-xl border border-border bg-card/95 p-1 shadow-xl backdrop-blur"
        >
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-3">
              {/* Skeleton rows give perceived-perf without a spinner */}
              <div className="flex w-full flex-col gap-2">
                {[80, 60, 72].map((w) => (
                  <div
                    key={w}
                    className="skeleton-pulse h-3 rounded"
                    style={{ width: `${w}%` }}
                  />
                ))}
              </div>
            </div>
          ) : error !== null ? (
            <p className="px-3 py-3 text-sm text-destructive">{error}</p>
          ) : results.length === 0 ? (
            <p className="px-3 py-3 text-sm text-muted-foreground">
              No memories match &ldquo;{query}&rdquo; yet.
            </p>
          ) : (
            <div className="flex flex-col">
              {results.map((result, index) => (
                <SearchResultRow
                  key={result.problem_id}
                  id={`${listboxId}-option-${index}`}
                  result={result}
                  query={query}
                  active={index === activeIndex}
                  isLast={index === results.length - 1}
                  onMouseEnter={() => setActiveIndex(index)}
                  onSelect={() => selectResult(result)}
                />
              ))}
              {/* Keyboard hint footer */}
              <div className="mt-0.5 border-t border-border px-3 py-1.5 flex items-center gap-3 text-[11px] text-muted-foreground/60">
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-border bg-muted px-1 py-px font-mono text-[10px] leading-tight">
                    ↑
                  </kbd>
                  <kbd className="rounded border border-border bg-muted px-1 py-px font-mono text-[10px] leading-tight">
                    ↓
                  </kbd>
                  navigate
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-border bg-muted px-1 py-px font-mono text-[10px] leading-tight">
                    ↵
                  </kbd>
                  open
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-border bg-muted px-1 py-px font-mono text-[10px] leading-tight">
                    Esc
                  </kbd>
                  close
                </span>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

const tierLabel: Record<"high" | "med" | "low", string> = {
  high: "high confidence",
  med: "medium confidence",
  low: "low confidence",
};

/**
 * Highlight matched substring in plain text.
 * Returns an array of {text, highlight} segments.
 */
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
            className="bg-transparent font-medium text-[hsl(0_50%_72%)]"
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

function SearchResultRow({
  id,
  result,
  query,
  active,
  isLast,
  onMouseEnter,
  onSelect,
}: {
  id: string;
  result: SearchResult;
  query: string;
  active: boolean;
  isLast: boolean;
  onMouseEnter: () => void;
  onSelect: () => void;
}) {
  const tier = result.best_solution
    ? getConfidenceTier(result.best_solution.confidence)
    : null;
  const confidencePct = result.best_solution
    ? Math.round(result.best_solution.confidence * 100)
    : null;

  // description_preview may contain markdown — extract plain text for highlighting
  // TitleMarkdown handles rendering; we pass query for the plain-text tag line only.
  const plainTitle = result.description_preview.replace(/[*_`~#[\]()]/g, "");

  return (
    <Link
      id={id}
      role="option"
      aria-selected={active}
      tabIndex={-1}
      href={`/memories/${result.problem_id}`}
      onClick={(event) => {
        event.preventDefault();
        onSelect();
      }}
      onMouseEnter={onMouseEnter}
      className={cn(
        "flex items-start gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
        // Active state uses a subtle coral-tinted left border + bg
        active
          ? "bg-white/[0.07] shadow-[inset_2px_0_0_hsl(0_50%_58%/0.6)]"
          : "hover:bg-white/[0.04]",
        // Separate rows with a hairline except last
        !isLast && "mb-px",
        focusRing,
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm leading-snug text-foreground">
          {query &&
          !result.description_preview.includes("*") &&
          !result.description_preview.includes("`") ? (
            <HighlightedText text={plainTitle} query={query} />
          ) : (
            <TitleMarkdown content={result.description_preview} insideLink />
          )}
        </div>
        {result.tags.length > 0 ? (
          <p className="mt-1 truncate text-[11px] text-muted-foreground">
            <HighlightedText
              text={result.tags.slice(0, 4).join(" · ")}
              query={query}
            />
          </p>
        ) : null}
      </div>
      {tier && confidencePct !== null ? (
        <Badge
          variant={tier}
          aria-label={`Best solution ${tierLabel[tier]} (${confidencePct} percent)`}
          className="mt-0.5 shrink-0"
        >
          {confidencePct}%
        </Badge>
      ) : (
        <Badge variant="low" className="mt-0.5 shrink-0">
          new
        </Badge>
      )}
    </Link>
  );
}
