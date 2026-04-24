const path = require("node:path");

/** @type {import("next").NextConfig} */
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");

const nextConfig = {
  /**
   * Pin Turbopack’s filesystem + module root to this app (`frontend/`), not a parent
   * directory that happens to contain a lockfile (e.g. monorepo root).
   * @see https://nextjs.org/docs/app/api-reference/config/next-config-js/turbopack
   */
  turbopack: {
    root: path.resolve(__dirname),
    // Belt-and-suspenders: force Tailwind PostCSS deps to this package’s node_modules.
    resolveAlias: {
      tailwindcss: path.join(__dirname, "node_modules", "tailwindcss"),
      "@tailwindcss/postcss": path.join(__dirname, "node_modules", "@tailwindcss", "postcss"),
    },
  },
  /**
   * Allow dev-only assets when using http://127.0.0.1 (default is localhost-oriented).
   * @see https://nextjs.org/docs/app/api-reference/config/next-config-js/allowedDevOrigins
   */
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    if (!apiBase) {
      return [];
    }
    return {
      beforeFiles: [
        // Canonical frontend edit URL, served by backend template without URL jump.
        {
          source: "/offertes/:quoteId/bewerken",
          destination: `${apiBase}/app/leads/:quoteId/edit-estimate`,
        },
        // Keep template submit target and static stylesheet functional on frontend origin.
        {
          source: "/app/quotes/:quoteId/edit",
          destination: `${apiBase}/app/quotes/:quoteId/edit`,
        },
        {
          source: "/static/:path*",
          destination: `${apiBase}/static/:path*`,
        },
      ],
    };
  },
};

module.exports = nextConfig;
