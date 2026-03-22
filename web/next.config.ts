import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname, "../"),
  experimental: {
    optimizePackageImports: [
      "@radix-ui/react-label",
      "@radix-ui/react-slot",
      "class-variance-authority",
      "clsx",
      "react-markdown",
      "remark-gfm",
      "sonner",
      "tailwind-merge",
    ],
  },
};

export default nextConfig;
