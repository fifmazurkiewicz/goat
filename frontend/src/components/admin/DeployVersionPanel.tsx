import { ExternalLink } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdminDeployInfo } from "@/hooks/useAdmin";
import {
  deployCommitsMatch,
  deployLabelsMatch,
  getFrontendDeployInfo,
  gitCommitUrl,
  type DeployInfo,
} from "@/lib/deploy-info";

function DeployRow({ info }: { info: DeployInfo }) {
  const commitUrl = gitCommitUrl(info);
  const label = info.component === "frontend" ? "Frontend (Vercel)" : "Backend (Render)";

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="min-w-[9rem] font-medium text-muted-foreground">{label}</span>
      <Badge variant="default" className="font-mono text-sm">
        v{info.app_version}
      </Badge>
      {info.git_sha ? (
        <Badge variant="secondary" className="font-mono text-xs">
          {info.git_sha}
        </Badge>
      ) : null}
      {info.git_branch ? <Badge variant="outline">{info.git_branch}</Badge> : null}
      {info.environment ? <span className="text-muted-foreground">({info.environment})</span> : null}
      {commitUrl ? (
        <a
          href={commitUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
        >
          GitHub
          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
        </a>
      ) : null}
    </div>
  );
}

/** Semver comparison of FE vs API; commit is treated as deploy metadata. */
export function DeployVersionPanel() {
  const { data: apiInfo, isLoading, isError } = useAdminDeployInfo();
  const frontendInfo = getFrontendDeployInfo();

  const apiDeploy: DeployInfo | null = apiInfo
    ? {
        component: "api",
        app_version: apiInfo.app_version,
        environment: apiInfo.environment,
        git_sha: apiInfo.git_sha,
        git_sha_full: apiInfo.git_sha_full,
        git_branch: apiInfo.git_branch,
        build_time: apiInfo.build_time,
        git_repo: apiInfo.git_repo,
      }
    : null;

  const versionMismatch = apiDeploy ? !deployLabelsMatch(frontendInfo, apiDeploy) : false;
  const commitMismatch =
    apiDeploy && !versionMismatch ? !deployCommitsMatch(frontendInfo, apiDeploy) : false;

  return (
    <Card className="mt-6">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Wersja aplikacji</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <DeployRow info={frontendInfo} />
        {isLoading ? <p className="text-sm text-muted-foreground">Ładowanie wersji API…</p> : null}
        {isError ? (
          <p className="text-sm text-destructive">Nie udało się pobrać wersji backendu.</p>
        ) : null}
        {apiDeploy ? <DeployRow info={apiDeploy} /> : null}
        {versionMismatch ? (
          <Alert variant="destructive">
            <AlertTitle>Różne wersje frontendu i API</AlertTitle>
            <AlertDescription>
              Frontend: v{frontendInfo.app_version}, API: v{apiDeploy?.app_version ?? "?"} — sprawdź
              deploy Vercel/Render albo podnieś <code className="text-xs">backend/VERSION</code> i
              wdróż oba serwisy.
            </AlertDescription>
          </Alert>
        ) : null}
        {commitMismatch ? (
          <Alert variant="warning">
            <AlertTitle>Ta sama wersja, różne commity</AlertTitle>
            <AlertDescription>
              Semver się zgadza, ale buildy mogą pochodzić z różnych commitów — upewnij się, że
              testujesz oczekiwany deploy.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
