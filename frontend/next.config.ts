import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// Content-Security-Policy (§14). Everything is served from this origin (the API through the
// /api rewrite, fonts self-hosted by next/font). Next.js's inline bootstrap scripts need
// 'unsafe-inline' without nonces; external scripts, framing and plugins are still refused.
// Dev mode also needs 'unsafe-eval' (React refresh), so the policy is production-only.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  ...(process.env.NODE_ENV === "production"
    ? [
        { key: "Content-Security-Policy", value: CSP },
        { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
      ]
    : []),
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  experimental: {
    // Next buffers proxied request bodies and drops the connection past this size (default
    // 10 MB). Bills may be 10 MB plus multipart overhead; FastAPI enforces the real 10 MB
    // limit with a clean 413 (ARCHITECTURE §5.1, Q-9). Verified locally in M1.
    proxyClientMaxBodySize: "12mb",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Same-origin API: the browser only ever talks to this app; FastAPI sits behind it (§1).
  // BACKEND_URL is server-only (no NEXT_PUBLIC_ prefix).
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: SECURITY_HEADERS },
      // Status links carry a secret in the URL (§12): never send it on as a referrer, never index.
      // Listed after the default so these values win for the same header names.
      {
        source: "/:locale/s/:token*",
        headers: [
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "Cache-Control", value: "no-store" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
