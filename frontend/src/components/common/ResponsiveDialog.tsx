import type { ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";

interface ResponsiveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * `Sheet` (bottom) na mobile / niskim ekranie zamiast wyśrodkowanego `Dialog`.
 * Jeden scroller (body), footer przyklejony nad safe area — klawiatura nie gubi Zapisz.
 */
export function ResponsiveDialog({ open, onOpenChange, title, description, children, footer, className }: ResponsiveDialogProps) {
  const isMobile = useIsMobile();

  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent
          side="bottom"
          className={cn(
            "flex h-[min(92dvh,100dvh)] max-h-[100dvh] flex-col gap-0 overflow-hidden p-4 pb-0",
            className
          )}
        >
          <SheetHeader className="shrink-0 pr-8 text-left">
            <SheetTitle>{title}</SheetTitle>
            {description ? <SheetDescription>{description}</SheetDescription> : null}
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-y-auto py-3">{children}</div>
          {footer ? (
            <SheetFooter className="shrink-0 border-t bg-background py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
              {footer}
            </SheetFooter>
          ) : (
            <div className="h-[env(safe-area-inset-bottom)] shrink-0" />
          )}
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={className}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        {children}
        {footer ? <DialogFooter>{footer}</DialogFooter> : null}
      </DialogContent>
    </Dialog>
  );
}
