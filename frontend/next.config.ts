import type { NextConfig } from "next";

// The API is reached at /api on the web app's own origin, in development and in production: the
// session cookie stays first-party and SameSite applies. API_ORIGIN is read at build time.
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8020";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
