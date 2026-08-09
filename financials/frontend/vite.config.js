import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `base: "./"` keeps every asset URL relative. HA Ingress serves the add-on
// from /api/hassio_ingress/<token>/, a prefix that is unknown at build time,
// so absolute asset paths would 404 there.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", sourcemap: false },
  server: { proxy: { "/api": { target: "http://localhost:8000" } } },
});
