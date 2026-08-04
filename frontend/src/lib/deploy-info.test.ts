import { describe, expect, it } from "vitest";

import { deployCommitsMatch, deployLabelsMatch, gitCommitUrl } from "@/lib/deploy-info";

describe("deploy-info", () => {
  it("builds GitHub commit URL", () => {
    expect(
      gitCommitUrl({ git_repo: "fifmazurkiewicz/goat", git_sha_full: "abc123def456" })
    ).toBe("https://github.com/fifmazurkiewicz/goat/commit/abc123def456");
  });

  it("detects semver mismatch between frontend and api", () => {
    const fe = {
      component: "frontend" as const,
      app_version: "0.2.0",
      git_sha: "aaa1111",
      git_sha_full: "aaa1111",
      git_branch: "main",
      git_repo: "fifmazurkiewicz/goat",
    };
    const api = {
      component: "api" as const,
      app_version: "0.1.0",
      git_sha: "aaa1111",
      git_sha_full: "aaa1111",
      git_branch: "main",
      git_repo: "fifmazurkiewicz/goat",
    };
    expect(deployLabelsMatch(fe, api)).toBe(false);
  });

  it("detects commit mismatch when semver matches", () => {
    const base = {
      app_version: "0.2.0",
      git_branch: "main",
      git_repo: "fifmazurkiewicz/goat",
    };
    const fe = { component: "frontend" as const, ...base, git_sha: "aaa1111", git_sha_full: "aaa1111" };
    const api = { component: "api" as const, ...base, git_sha: "bbb2222", git_sha_full: "bbb2222" };
    expect(deployLabelsMatch(fe, api)).toBe(true);
    expect(deployCommitsMatch(fe, api)).toBe(false);
  });
});
