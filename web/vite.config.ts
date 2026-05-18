import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/",
  plugins: [tailwindcss(), react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          motion: ["framer-motion"],
          virtuoso: ["react-virtuoso"],
          icons: ["lucide-react"]
        }
      }
    }
  },
  test: {
    environment: "jsdom",
    fileParallelism: false,
    maxWorkers: 1,
    setupFiles: "./src/test/setup.ts",
    testTimeout: 10000
  }
});
