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
    <div className="space-y-6">
      <SearchBar query={query} loading={loading} onQueryChange={setQuery} onSearch={handleSearch} />

      <section className="space-y-4">
        {results.map((result) => (
          <Card key={result.thread_id}>
            <CardHeader>
              <CardTitle>
                <Link href={`/threads/${result.thread_id}`} className="hover:underline">
                  {result.title}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <p>{result.body_preview}</p>
                <p className="text-sm text-muted-foreground">
                  Similarity: {(result.similarity_score * 100).toFixed(1)}%
                </p>
                <div className="flex flex-wrap gap-2">
                  {result.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
                {result.top_solution ? (
                  <Card>
                    <CardHeader>
                      <CardTitle>Top Solution</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p>{result.top_solution.content_preview}</p>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
