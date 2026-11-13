import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/ and https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    // `globals` lets React Testing Library register its automatic cleanup (afterEach).
    globals: true,
    setupFiles: ["./src/setupTests.js"],
    testTimeout: 15000,
    hookTimeout: 30000,
    teardownTimeout: 10000,
    pool: "forks",
    maxWorkers: 2,
  },
});
