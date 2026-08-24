export interface DeployInfo {
  component: "frontend" | "api";
  app_version: string;
  environment?: string;
  git_sha: string | null;
  git_sha_full: string | null;
  git_branch: string | null;
  build_time?: string | null;
  git_repo: string;
}

export function getFrontendDeployInfo(): DeployInfo {
  const raw =
    typeof __FRONTEND_DEPLOY_INFO__ !== "undefined"
      ? __FRONTEND_DEPLOY_INFO__
      : {
          app_version: "0.0.0-dev",
          git_sha: "dev",
          git_sha_full: "dev",
          git_branch: "local",
          git_repo: "fifmazurkiewicz/goat",
        };

  return { component: "frontend", ...raw };
}

export function gitCommitUrl(info: Pick<DeployInfo, "git_repo" | "git_sha_full">): string | null {
  const sha = info.git_sha_full?.trim();
  if (!sha || sha === "dev" || sha === "test") return null;
  return `https://github.com/${info.git_repo}/commit/${sha}`;
}

/** FE vs API semver — the commit is only diagnostic metadata. */
export function deployLabelsMatch(a: DeployInfo, b: DeployInfo): boolean {
  if (!a.app_version || !b.app_version) return true;
  if (a.app_version.endsWith("-dev") || b.app_version.endsWith("-dev")) return true;
  return a.app_version === b.app_version;
}

export function deployCommitsMatch(a: DeployInfo, b: DeployInfo): boolean {
  if (!a.git_sha || !b.git_sha || a.git_sha === "dev" || b.git_sha === "dev") return true;
  return a.git_sha === b.git_sha && (a.git_branch ?? "") === (b.git_branch ?? "");
}
