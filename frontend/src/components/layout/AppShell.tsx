import { useEffect } from "react";
import { Moon, ShieldAlert, Sun } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAccount } from "@/hooks/useAccount";
import { usePlanGenerationPolling } from "@/hooks/usePlans";
import { useUsage } from "@/hooks/useUsage";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/useAuthStore";
import { useThemeStore } from "@/store/useThemeStore";
import { useUsageLimitsStore } from "@/store/useUsageLimitsStore";

const NAV_ITEMS = [
  { to: "/personas", label: "Persony" },
  { to: "/chat", label: "Czat" },
  { to: "/plans", label: "Plany" },
  { to: "/results", label: "Wyniki" },
  { to: "/settings", label: "Ustawienia" },
];

/**
 * App shell / root layout dla tras chronionych. `usePlanGenerationPolling` żyje TUTAJ
 * (nie w /plans) — mountowany raz, przetrwa nawigację między stronami
 * (docs/technical/frontend.md sekcja 2 i 5). `useUsage` odpytuje budżet USD raz na
 * poziomie shellu i zasila `useUsageLimitsStore`. `GET /account` ustawia `isAdmin`.
 */
export function AppShell() {
  const session = useAuthStore((state) => state.session);
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const setIsAdmin = useAuthStore((state) => state.setIsAdmin);
  const theme = useThemeStore((state) => state.theme);
  const toggleTheme = useThemeStore((state) => state.toggleTheme);
  const isNearLimit = useUsageLimitsStore((state) => state.isNearLimit);
  const limits = useUsageLimitsStore((state) => state.limits);

  const { data: account } = useAccount();

  useEffect(() => {
    if (!session) {
      setIsAdmin(false);
      return;
    }
    if (account) {
      setIsAdmin(account.is_admin);
    }
  }, [session, account, setIsAdmin]);

  useUsage();
  usePlanGenerationPolling();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container flex h-14 items-center justify-between gap-4">
          <NavLink
            to="/chat"
            className="shrink-0 font-semibold text-foreground transition-colors hover:opacity-80"
          >
            Coach
          </NavLink>
          <nav className="flex flex-1 gap-4 overflow-x-auto text-sm">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "shrink-0 whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground",
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
                    "flex shrink-0 items-center gap-1 whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground",
                    isActive && "font-medium text-foreground"
                  )
                }
              >
                <ShieldAlert className="h-3.5 w-3.5" /> Admin
              </NavLink>
            ) : null}
          </nav>
          <div className="flex shrink-0 items-center gap-2">
            {limits ? (
              <Badge variant={isNearLimit ? "destructive" : "secondary"} className="tabular-nums">
                ${limits.cost_usd_used.toFixed(2)} / ${limits.usage_budget_usd.toFixed(0)}
              </Badge>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Przełącz na motyw jasny" : "Przełącz na motyw ciemny"}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
