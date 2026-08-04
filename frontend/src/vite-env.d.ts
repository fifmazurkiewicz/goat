/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare const __FRONTEND_DEPLOY_INFO__: {
  git_sha: string;
  git_sha_full: string;
  git_branch: string;
  git_repo: string;
};
