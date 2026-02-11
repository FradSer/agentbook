"use client";

import { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type SearchBarProps = {
  query: string;
  loading: boolean;
  onQueryChange: (value: string) => void;
  onSearch: () => Promise<void>;
};

export function SearchBar({ query, loading, onQueryChange, onSearch }: SearchBarProps) {
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSearch();
  }

  return (
    <form className="flex gap-2" onSubmit={handleSubmit}>
      <Input
        aria-label="Search knowledge base"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="ModuleNotFoundError fastmcp"
      />
      <Button type="submit" disabled={loading || query.trim().length === 0}>
        Search
      </Button>
    </form>
  );
}
