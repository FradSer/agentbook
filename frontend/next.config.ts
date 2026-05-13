import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  outputFileTracingRoot: path.join(__dirname, "../"),
  experimental: {
    optimizePackageImports: [
      "@radix-ui/react-slot",
      "class-variance-authority",
      "clsx",
      "react-markdown",
      "remark-gfm",
      "sonner",
      "tailwind-merge",
    ],
  },
  async redirects() {
    return [
      {
        source: "/problems",
        destination: "/memories",
        permanent: true, // Next.js maps permanent:true to HTTP 308
      },
      {
        source: "/problems/:id",
        destination: "/memories/:id",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
