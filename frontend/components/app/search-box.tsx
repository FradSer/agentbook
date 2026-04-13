"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type Variant = "default" | "hero";

export function SearchBox({
  initialQuery,
  variant = "default",
}: {
  initialQuery: string;
  variant?: Variant;
}) {
  const router = useRouter();
  const [value, setValue] = useState(initialQuery);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  const isHero = variant === "hero";

  return (
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
        onChange={(event) => setValue(event.target.value)}
        className={cn(isHero && "h-12 text-base")}
      />
      <Button type="submit" size={isHero ? "lg" : "default"}>
        Search
      </Button>
    </form>
  );
}
