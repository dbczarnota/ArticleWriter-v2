import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: "..",
  server: {
    proxy: {
      "/v2": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
