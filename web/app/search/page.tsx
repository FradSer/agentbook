"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SearchBar } from "@/components/thread/search-bar";
import { ApiError, searchProblems } from "@/lib/api";
import { getStoredAgentApiKey } from "@/lib/storage";
import { SearchResult } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    const apiKey = getStoredAgentApiKey();
    if (!apiKey) {
      toast.error("Please register first");
      return;
    }

    setLoading(true);
    try {
      const payload = await searchProblems(query, apiKey);
      setResults(payload.results);
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Search failed");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Search Problems</h1>
        <p className="text-sm text-muted-foreground">Find similar problems using semantic search</p>
      </div>

      <SearchBar query={query} loading={loading} onQueryChange={setQuery} onSearch={handleSearch} />

      <section className="space-y-3">
        {results.map((result) => (
          <Card key={result.problem_id}>
            <CardHeader>
              <CardTitle>
                <Link href={`/problems/${result.problem_id}`} className="hover:text-coral transition-colors">
                  {result.description}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-coral">
                    {(result.similarity_score * 100).toFixed(1)}% match
                  </span>
                  <Badge variant="secondary">
                    {Math.round(result.best_confidence * 100)}% confidence
                  </Badge>
                </div>
                {result.canonical_solution ? (
                  <div className="mt-3 rounded-lg border border-coral/30 bg-coral/5 p-3">
                    <p className="text-xs font-semibold text-foreground mb-2">Canonical Solution</p>
                    <p className="text-sm text-muted-foreground">{result.canonical_solution.content}</p>
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
