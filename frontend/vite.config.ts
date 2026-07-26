import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const repositoryRoot = resolve(import.meta.dirname, "..");
const gitMetadataDirectory = process.env.GIT_METADATA_DIR
  ? resolve(process.env.GIT_METADATA_DIR)
  : resolve(repositoryRoot, ".git");

const buildInfo = {
  commit: readShortCommit(gitMetadataDirectory),
  timestamp: new Date().toISOString(),
};

export default defineConfig({
  define: {
    __BUILD_INFO__: JSON.stringify(buildInfo),
  },
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
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
  },
});

function readShortCommit(gitDirectory: string): string {
  const headPath = resolve(gitDirectory, "HEAD");
  if (!existsSync(headPath)) return "unknown";

  const head = readFileSync(headPath, "utf8").trim();
  if (!head.startsWith("ref: ")) return head.slice(0, 7);

  const reference = head.slice(5);
  const looseReferencePath = resolve(gitDirectory, reference);
  if (existsSync(looseReferencePath)) {
    return readFileSync(looseReferencePath, "utf8").trim().slice(0, 7);
  }

  const packedReferencesPath = resolve(gitDirectory, "packed-refs");
  if (!existsSync(packedReferencesPath)) return "unknown";
  const packedReference = readFileSync(packedReferencesPath, "utf8")
    .split("\n")
    .find((line: string) => line.endsWith(` ${reference}`));
  return packedReference?.split(" ")[0]?.slice(0, 7) ?? "unknown";
}
