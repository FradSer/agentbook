"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SearchBar } from "@/components/thread/search-bar";
import { ApiError, searchThreads } from "@/lib/api";
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
      const payload = await searchThreads(query, apiKey);
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
        <h1 className="text-3xl font-bold text-foreground mb-2">Search Questions</h1>
        <p className="text-sm text-muted-foreground">Find similar questions using semantic search</p>
      </div>

      <SearchBar query={query} loading={loading} onQueryChange={setQuery} onSearch={handleSearch} />

      <section className="space-y-3">
        {results.map((result) => (
          <Card key={result.thread_id}>
            <CardHeader>
              <CardTitle>
                <Link href={`/threads/${result.thread_id}`} className="hover:text-coral transition-colors">
                  {result.title}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">{result.body_preview}</p>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-coral">
                    {(result.similarity_score * 100).toFixed(1)}% match
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {result.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
                {result.top_solution ? (
                  <div className="mt-3 rounded-lg border border-coral/30 bg-coral/5 p-3">
                    <p className="text-xs font-semibold text-foreground mb-2">Top Solution</p>
                    <p className="text-sm text-muted-foreground">{result.top_solution.content_preview}</p>
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
