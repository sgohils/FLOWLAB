import { fileURLToPath } from "node:url";
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

/**
 * Tests reuse the application's own Vite config, so the `@` alias and the React
 * plugin are identical to the build and a test can never resolve a module the
 * bundler would not.
 */
export default defineConfig(
  mergeConfig(viteConfig, {
    test: {
      environment: "jsdom",
      // No globals: every test names what it uses, so a deleted import is an
      // error rather than a mystery ReferenceError.
      globals: false,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      restoreMocks: true,
    },
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
  }),
);
