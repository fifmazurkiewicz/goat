import { useEffect, useRef, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAccount, useUpdateAccount } from "@/hooks/useAccount";
import { useThemeStore } from "@/store/useThemeStore";
import { cn } from "@/lib/utils";

const DEBOUNCE_MS = 600;

const THEME_OPTIONS = [
  { key: "light", label: "Jasny" },
  { key: "dark", label: "Ciemny" },
] as const;

/**
 * Nick (input, PATCH /api/v1/account debounced) + przełącznik motywu jasny/ciemny
 * (zustand `useThemeStore`, PERSYSTOWANY WYŁĄCZNIE w localStorage, ADR-15).
 * docs/technical/frontend.md sekcja 7a.
 */
export function AccountSettingsCard() {
  const { data: account } = useAccount();
  const updateAccount = useUpdateAccount();
  const theme = useThemeStore((state) => state.theme);
  const setTheme = useThemeStore((state) => state.setTheme);

  const [nick, setNick] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const isFirstSync = useRef(true);

  useEffect(() => {
    if (account && isFirstSync.current) {
      setNick(account.nick ?? "");
      isFirstSync.current = false;
    }
  }, [account]);

  function handleNickChange(value: string) {
    setNick(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      updateAccount.mutate({ nick: value || null });
    }, DEBOUNCE_MS);
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Ustawienia konta</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="nick">Nick</Label>
          <Input
            id="nick"
            value={nick}
            onChange={(e) => handleNickChange(e.target.value)}
            placeholder={account?.email}
          />
        </div>
        <div className="space-y-1.5">
          <Label id="theme-label">Motyw</Label>
          <div role="radiogroup" aria-labelledby="theme-label" className="inline-flex rounded-md border p-1">
            {THEME_OPTIONS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setTheme(option.key)}
                className={cn(
                  "rounded-sm px-3 py-1.5 text-sm transition-colors",
                  theme === option.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
