import type { NextConfig } from "next";

// 127.0.0.1 rather than localhost, which stalls on the development machine.
const API_ORIGIN = "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  output: "standalone",
  agentRules: false,
  experimental: {
    // A question can wait on the main model and then the fallback, 60 seconds each.
    proxyTimeout: 150_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
