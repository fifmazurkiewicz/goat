import { useEffect } from "react";
import { Moon, ShieldAlert, Sun } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAccount } from "@/hooks/useAccount";
import { usePlanGenerationPolling, usePlanGenerationSync } from "@/hooks/usePlans";
import { useChatTurnRunner } from "@/hooks/useChatTurnRunner";
import { useUsage } from "@/hooks/useUsage";
import { useVisualViewportHeight } from "@/hooks/useVisualViewportHeight";
import { ChatTurnBanner } from "@/components/chat/ChatTurnBanner";
import { isChatPath } from "@/lib/layout";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/useAuthStore";
import { useThemeStore } from "@/store/useThemeStore";
import { useUsageLimitsStore } from "@/store/useUsageLimitsStore";

const NAV_ITEMS = [
  { to: "/personas", label: "Persony" },
  { to: "/chat", label: "Czat" },
  { to: "/plans", label: "Plany" },
  { to: "/results", label: "Wyniki" },
  { to: "/profile", label: "Profil" },
  { to: "/settings", label: "Ustawienia" },
];

/**
 * App shell / root layout dla tras chronionych. `usePlanGenerationPolling` żyje TUTAJ
 * (nie w /plans) — mountowany raz, przetrwa nawigację między stronami
 * (docs/technical/frontend.md sekcja 2 i 5). `useUsage` odpytuje budżet USD raz na
 * poziomie shellu i zasila `useUsageLimitsStore`. `GET /account` ustawia `isAdmin`.
 */
export function AppShell() {
  const location = useLocation();
  const chatMode = isChatPath(location.pathname);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const setIsAdmin = useAuthStore((state) => state.setIsAdmin);
  const theme = useThemeStore((state) => state.theme);
  const toggleTheme = useThemeStore((state) => state.toggleTheme);
  const isNearLimit = useUsageLimitsStore((state) => state.isNearLimit);
  const limits = useUsageLimitsStore((state) => state.limits);

  useVisualViewportHeight();

  const { data: account } = useAccount();

  useEffect(() => {
    if (!isAuthenticated) {
      setIsAdmin(false);
      return;
    }
    if (account) {
      setIsAdmin(account.is_admin);
    }
  }, [isAuthenticated, account, setIsAdmin]);

  useUsage();
  usePlanGenerationSync();
  usePlanGenerationPolling();
  useChatTurnRunner();

  return (
    <div
      className="flex h-dvh flex-col overflow-hidden bg-background"
      style={{ height: "var(--app-height, 100dvh)" }}
    >
      <header className="shrink-0 border-b pt-[env(safe-area-inset-top)]">
        <div className="flex h-12 items-center gap-2 px-3 sm:container sm:h-14 sm:justify-between sm:gap-4">
          <NavLink
            to="/chat"
            className="inline-flex min-h-11 shrink-0 items-center font-semibold text-foreground transition-colors hover:opacity-80"
          >
            Coach
          </NavLink>
          <nav className="flex min-h-11 min-w-0 flex-1 items-center gap-1 overflow-x-auto text-sm [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:gap-3">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "inline-flex min-h-11 shrink-0 items-center whitespace-nowrap px-2 text-muted-foreground transition-colors hover:text-foreground",
                    isActive && "font-medium text-foreground"
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            {isAdmin ? (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  cn(
                    "inline-flex min-h-11 shrink-0 items-center gap-1 whitespace-nowrap px-2 text-muted-foreground transition-colors hover:text-foreground",
                    isActive && "font-medium text-foreground"
                  )
                }
              >
                <ShieldAlert className="h-3.5 w-3.5" /> Admin
              </NavLink>
            ) : null}
          </nav>
          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            {limits ? (
              <Badge variant={isNearLimit ? "destructive" : "secondary"} className="hidden tabular-nums sm:inline-flex">
                ${limits.cost_usd_used.toFixed(2)} / ${limits.usage_budget_usd.toFixed(0)}
              </Badge>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="min-h-11 min-w-11"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Przełącz na motyw jasny" : "Przełącz na motyw ciemny"}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>
      <div className="shrink-0">
        <ChatTurnBanner />
      </div>
      <main
        className={cn(
          "min-h-0 flex-1",
          chatMode ? "flex flex-col overflow-hidden" : "overflow-y-auto"
        )}
      >
        <Outlet />
      </main>
    </div>
  );
}
