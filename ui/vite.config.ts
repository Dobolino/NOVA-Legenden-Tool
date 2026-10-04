import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the Python server runs on port 8765 (python -m nova_legend --server)
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  build: { outDir: "dist", emptyOutDir: true },
});
