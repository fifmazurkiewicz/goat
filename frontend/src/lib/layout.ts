/** Whether the route is the chat screen — then `main` must not scroll the page. */
export function isChatPath(pathname: string): boolean {
  return pathname === "/chat" || pathname.startsWith("/chat/");
}

/** Shared page gutter in AppShell (mobile: smaller padding + safe area). */
export const PAGE_SHELL_CLASS =
  "container py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] md:py-10";

export const PAGE_TITLE_CLASS = "text-2xl font-semibold tracking-tight md:text-3xl";
