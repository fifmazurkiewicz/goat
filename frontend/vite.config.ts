import { execSync } from "node:child_process";
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

function tryGit(command: string): string | null {
  try {
    return execSync(command, { encoding: "utf-8", cwd: path.resolve(__dirname, "..") }).trim();
  } catch {
    return null;
  }
}

function resolveFrontendDeployInfo() {
  const shaFull =
    process.env.VERCEL_GIT_COMMIT_SHA?.trim() ||
    process.env.APP_GIT_SHA?.trim() ||
    tryGit("git rev-parse HEAD") ||
    null;
  const branch =
    process.env.VERCEL_GIT_COMMIT_REF?.trim() ||
    process.env.VERCEL_GIT_BRANCH?.trim() ||
    process.env.APP_GIT_BRANCH?.trim() ||
    tryGit("git rev-parse --abbrev-ref HEAD") ||
    null;

  return {
    git_sha: shaFull ? (shaFull.length <= 12 ? shaFull : shaFull.slice(0, 7)) : "dev",
    git_sha_full: shaFull ?? "dev",
    git_branch: branch ?? "local",
    git_repo: process.env.APP_GIT_REPO?.trim() || "fifmazurkiewicz/goat",
  };
}

const frontendDeployInfo = resolveFrontendDeployInfo();

export default defineConfig({
  define: {
    __FRONTEND_DEPLOY_INFO__: JSON.stringify(frontendDeployInfo),
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
