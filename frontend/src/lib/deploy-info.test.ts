import { describe, expect, it } from "vitest";

import { deployLabelsMatch, gitCommitUrl } from "@/lib/deploy-info";

describe("deploy-info", () => {
  it("builds GitHub commit URL", () => {
    expect(
      gitCommitUrl({ git_repo: "fifmazurkiewicz/goat", git_sha_full: "abc123def456" })
    ).toBe("https://github.com/fifmazurkiewicz/goat/commit/abc123def456");
  });

  it("detects mismatch between frontend and api", () => {
    const fe = {
      component: "frontend" as const,
      git_sha: "aaa1111",
      git_sha_full: "aaa1111",
      git_branch: "main",
      git_repo: "fifmazurkiewicz/goat",
    };
    const api = {
      component: "api" as const,
      git_sha: "bbb2222",
      git_sha_full: "bbb2222",
      git_branch: "main",
      git_repo: "fifmazurkiewicz/goat",
    };
    expect(deployLabelsMatch(fe, api)).toBe(false);
  });
});
