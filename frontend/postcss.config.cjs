const path = require("node:path");

/**
 * Tailwind v4 PostCSS uses `base` for package resolution and scanning; it defaults to
 * `process.cwd()`, which is often the monorepo root when the editor or a script starts
 * Next from `C:\...\Inversiq` instead of `...\Inversiq\frontend`. Pin `base` to this
 * package directory so `tailwindcss` always resolves under `frontend/node_modules`.
 *
 * @type {import("postcss-load-config").Config}
 */
module.exports = {
  plugins: {
    "@tailwindcss/postcss": {
      base: path.resolve(__dirname),
    },
  },
};
