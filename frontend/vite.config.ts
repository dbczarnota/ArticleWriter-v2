import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
  },
  envDir: "..",
  server: {
    port: 5173,
    proxy: {
      "/v2": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
