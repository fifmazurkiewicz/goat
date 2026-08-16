import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

/**
 * Toasty side-effectowe (np. zmiana statusu generowania planu, `usePlanGenerationStore`
 * — docs/technical/frontend.md sekcja 2). Motyw czytany z klasy `.dark` na <html>
 * (useThemeStore, ADR-15) zamiast osobnego providera motywu.
 */
function Toaster({ ...props }: ToasterProps) {
  const isDark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");

  return (
    <Sonner
      theme={isDark ? "dark" : "light"}
      className="toaster group"
      offset={{ bottom: "calc(12px + env(safe-area-inset-bottom, 0px))" }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
