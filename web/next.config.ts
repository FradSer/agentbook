import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname, "../"),
  experimental: {
    optimizePackageImports: [
      "@radix-ui/react-label",
      "@radix-ui/react-slot",
      "react-markdown",
      "remark-gfm",
      "sonner",
    ],
  },
};

export default nextConfig;
