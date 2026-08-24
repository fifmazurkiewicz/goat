import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAccount, useUpdateAccount } from "@/hooks/useAccount";
import { getErrorMessage } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/useAuthStore";
import { useThemeStore } from "@/store/useThemeStore";

const THEME_OPTIONS = [
  { key: "light", label: "Jasny" },
  { key: "dark", label: "Ciemny" },
] as const;

/**
 * Nickname (input + explicit "Save nick") + theme (localStorage, ADR-15).
 * docs/technical/frontend.md section 7a.
 */
export function AccountSettingsCard() {
  const { data: account } = useAccount();
  const updateAccount = useUpdateAccount();
  const userEmail = useAuthStore((state) => state.user?.email);
  const theme = useThemeStore((state) => state.theme);
  const setTheme = useThemeStore((state) => state.setTheme);

  const [nick, setNick] = useState("");
  const [syncedId, setSyncedId] = useState<string | null>(null);

  useEffect(() => {
    if (!account) return;
    if (syncedId !== account.id) {
      setNick(account.nick ?? "");
      setSyncedId(account.id);
    }
  }, [account, syncedId]);

  const savedNick = account?.nick ?? "";
  const isDirty = nick !== savedNick;

  async function handleSaveNick() {
    try {
      await updateAccount.mutateAsync({ nick: nick.trim() || null });
      toast.success("Zapisano nick");
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się zapisać nicka"));
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Ustawienia konta</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="nick">Nick</Label>
          <div className="flex flex-wrap gap-2">
            <Input
              id="nick"
              className="min-w-[12rem] flex-1"
              value={nick}
              onChange={(e) => setNick(e.target.value)}
              placeholder={userEmail ?? "Twój nick"}
              maxLength={100}
            />
            <Button
              type="button"
              onClick={() => void handleSaveNick()}
              disabled={!isDirty || updateAccount.isPending}
            >
              {updateAccount.isPending ? "Zapisywanie…" : "Zapisz nick"}
            </Button>
          </div>
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
                  theme === option.key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent"
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
