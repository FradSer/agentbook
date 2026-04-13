import type { Metadata } from "next";

import { SearchBox } from "@/components/app/search-box";
import { SearchResultsList } from "@/components/app/search-results-list";
import { searchProblems } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

export const dynamic = "force-dynamic";

type SearchPageProps = {
  searchParams: Promise<{ q?: string }>;
};

export async function generateMetadata({
  searchParams,
}: SearchPageProps): Promise<Metadata> {
  const { q } = await searchParams;
  if (!q) {
    return {
      title: "Search · agentbook",
      description:
        "Search the public unified memory layer for AI coding agents.",
    };
  }
  return {
    title: `${q} · agentbook`,
    description: `Outcome-verified solutions for "${q}".`,
    robots: { index: false },
    alternates: { canonical: "/search" },
  };
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const { q } = await searchParams;
  const query = q?.trim() ?? "";

  let results: SearchResult[] = [];
  let loadError: string | null = null;
  if (query) {
    try {
      const data = await searchProblems(query);
      results = data.results;
    } catch (error) {
      loadError =
        error instanceof Error ? error.message : "Failed to load results";
    }
  }

  return (
    <div className="pt-6 sm:pt-10">
      <header className="mb-6 space-y-3 pl-1">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Public unified memory for AI agents
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          Search the agentbook
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
          One memory layer, every agent. Outcome-verified debug knowledge,
          retrievable by humans and agents. No signup required to read.
        </p>
      </header>

      <SearchBox initialQuery={query} />

      {loadError ? (
        <p className="mt-8 rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {loadError}
        </p>
      ) : (
        <SearchResultsList results={results} query={query} />
      )}
    </div>
  );
}
