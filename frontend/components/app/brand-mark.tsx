"use client";

import { useEffect, useState } from "react";

import { GradientColorBlock } from "@/components/app/gradient-color-block";
import { gradientFromSeed } from "@/lib/utils";

const PLACEHOLDER =
  "linear-gradient(135deg, hsl(220 12% 22%) 0%, hsl(220 12% 28%) 100%)";

export function BrandMark() {
  const [seed, setSeed] = useState<string | null>(null);

  useEffect(() => {
    const id = crypto.randomUUID();
    queueMicrotask(() => {
      setSeed(id);
    });
  }, []);

  const background =
    seed === null
      ? PLACEHOLDER
      : (() => {
          const { from, to } = gradientFromSeed(seed);
          return `linear-gradient(135deg, ${from} 0%, ${to} 100%)`;
        })();

  return (
    <GradientColorBlock
      background={background}
      className="transition-[background] duration-300 ease-out"
      aria-hidden
    />
  );
}
