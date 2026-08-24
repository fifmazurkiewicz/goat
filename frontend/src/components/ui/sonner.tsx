import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

/**
 * Side-effect toasts (e.g. plan generation status changes, `usePlanGenerationStore`
 * — docs/technical/frontend.md section 2). Theme is read from the `.dark` class on
 * <html> (useThemeStore, ADR-15) instead of a dedicated theme provider.
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
