import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
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
