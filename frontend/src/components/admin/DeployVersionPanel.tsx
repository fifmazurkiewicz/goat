import { ExternalLink } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdminDeployInfo } from "@/hooks/useAdmin";
import { deployLabelsMatch, getFrontendDeployInfo, gitCommitUrl, type DeployInfo } from "@/lib/deploy-info";

function DeployRow({ info }: { info: DeployInfo }) {
  const commitUrl = gitCommitUrl(info);
  const label = info.component === "frontend" ? "Frontend (Vercel)" : "Backend (Render)";

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="min-w-[9rem] font-medium text-muted-foreground">{label}</span>
      <Badge variant="secondary" className="font-mono">
        {info.git_sha ?? "unknown"}
      </Badge>
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

/** Porównanie commitów FE vs API — szybka weryfikacja „czy testuję tę samą wersję”. */
export function DeployVersionPanel() {
  const { data: apiInfo, isLoading, isError } = useAdminDeployInfo();
  const frontendInfo = getFrontendDeployInfo();

  const apiDeploy: DeployInfo | null = apiInfo
    ? {
        component: "api",
        environment: apiInfo.environment,
        git_sha: apiInfo.git_sha,
        git_sha_full: apiInfo.git_sha_full,
        git_branch: apiInfo.git_branch,
        build_time: apiInfo.build_time,
        git_repo: apiInfo.git_repo,
      }
    : null;

  const mismatch = apiDeploy ? !deployLabelsMatch(frontendInfo, apiDeploy) : false;

  return (
    <Card className="mt-6">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Wersja deployu</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <DeployRow info={frontendInfo} />
        {isLoading ? <p className="text-sm text-muted-foreground">Ładowanie wersji API…</p> : null}
        {isError ? (
          <p className="text-sm text-destructive">Nie udało się pobrać wersji backendu.</p>
        ) : null}
        {apiDeploy ? <DeployRow info={apiDeploy} /> : null}
        {mismatch ? (
          <Alert variant="destructive">
            <AlertTitle>Różne commity frontendu i API</AlertTitle>
            <AlertDescription>
              Możesz testować inną wersję niż ta na produkcji — sprawdź deploy Vercel/Render albo
              odśwież oba serwisy.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
