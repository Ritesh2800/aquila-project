import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, /api and /files are forwarded to the FastAPI server.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      "/api": "http://localhost:8000",
      "/files": "http://localhost:8000",
    },
  },
});
