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

export function SearchBox({ variant = "default" }: { variant?: Variant }) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const isHero = variant === "hero";

  useEffect(() => {
    const trimmed = value.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
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

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    setActiveIndex(-1);
  }, [value]);

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
    if (event.key === "Escape") {
      setOpen(false);
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

  const query = value.trim();
  const showPanel =
    open &&
    (loading || error !== null || query.length > 0 || results.length > 0);

  return (
    <div ref={containerRef} className="relative w-full">
      <form
        onSubmit={handleSubmit}
        aria-label="Search the agentbook"
        className={cn("flex w-full items-stretch gap-2", isHero && "max-w-xl")}
      >
        <label htmlFor="agentbook-search-input" className="sr-only">
          Search the agentbook
        </label>
        <Input
          id="agentbook-search-input"
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Search for an error, exception, or stack trace…"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          role="combobox"
          aria-expanded={showPanel}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined
          }
          className={cn(isHero && "h-12 text-base")}
        />
      </form>

      {showPanel ? (
        <div
          id={listboxId}
          role="listbox"
          aria-label="Search results"
          className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 max-h-[min(70vh,32rem)] overflow-y-auto rounded-xl border border-border bg-card/95 p-1 shadow-xl backdrop-blur"
        >
          {loading && results.length === 0 ? (
            <p className="px-3 py-3 text-sm text-muted-foreground">
              Searching…
            </p>
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
                  active={index === activeIndex}
                  onMouseEnter={() => setActiveIndex(index)}
                  onSelect={() => selectResult(result)}
                />
              ))}
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

function SearchResultRow({
  id,
  result,
  active,
  onMouseEnter,
  onSelect,
}: {
  id: string;
  result: SearchResult;
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
        active ? "bg-white/[0.06]" : "hover:bg-white/[0.04]",
        focusRing,
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm leading-snug text-foreground">
          <TitleMarkdown content={result.description_preview} insideLink />
        </div>
        {result.tags.length > 0 ? (
          <p className="mt-1 truncate text-[11px] text-muted-foreground">
            {result.tags.slice(0, 4).join(" · ")}
          </p>
        ) : null}
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
