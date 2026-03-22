"use client";

import { useEffect, type ReactNode } from "react";

/**
 * Wide screens: lock document scroll so only .scroll-panel regions move.
 * Narrow screens: leave body scroll (WeChat / mobile) untouched.
 */
export default function ProblemDetailLayout({ children }: { children: ReactNode }) {
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const apply = () => {
      if (mq.matches) {
        document.documentElement.style.overflow = "hidden";
        document.body.style.overflow = "hidden";
      } else {
        document.documentElement.style.overflow = "";
        document.body.style.overflow = "";
      }
    };
    apply();
    mq.addEventListener("change", apply);
    return () => {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
      mq.removeEventListener("change", apply);
    };
  }, []);

  return <>{children}</>;
}
