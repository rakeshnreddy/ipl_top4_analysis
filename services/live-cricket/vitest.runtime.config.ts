import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";
export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: { bindings: { SCORE_PROVIDER: "none" } },
    }),
  ],
  test: { include: ["test/**/*.runtime.spec.ts"] },
});
