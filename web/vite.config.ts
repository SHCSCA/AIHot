import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/",
  plugins: [tailwindcss(), react()],
  test: {
    environment: "jsdom",
    fileParallelism: false,
    maxWorkers: 1,
    setupFiles: "./src/test/setup.ts",
    testTimeout: 10000
  }
});
