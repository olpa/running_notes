import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        index: resolve(import.meta.dirname, "index.html"),
        privacy: resolve(import.meta.dirname, "privacy.html"),
        terms: resolve(import.meta.dirname, "terms.html"),
      },
    },
  },
  server: {
    proxy: {
      "/auth": "http://localhost:8000",
      "/me": "http://localhost:8000",
      "/messages": "http://localhost:8000",
      "/record": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
  },
});
