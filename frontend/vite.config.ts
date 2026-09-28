import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const BACKEND = process.env.FLOWLAB_API ?? "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Proxy keeps the browser on a single origin in development, so no CORS
    // configuration is needed while working on the frontend.
    proxy: {
      "/api": {
        target: BACKEND,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        // Keep the charting library out of the app chunk so the first paint
        // does not wait for it.
        manualChunks: {
          charts: ["recharts"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
