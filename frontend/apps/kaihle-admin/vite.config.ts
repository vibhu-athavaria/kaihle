import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0", // reachable from outside container
    port: 3005, // must match docker-compose port mapping
    hmr: {
      host: "localhost", // ← browser connects back through Docker port mapping
      port: 3005,
    },
    watch: {
      usePolling: true, // fixes macOS Docker Desktop file event issue
      interval: 1000, // poll every 1s — balance between responsiveness and CPU
    },
  },
});
