import { useState } from "react";
import { format } from "date-fns";
import { pl } from "date-fns/locale";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { sessionListTitle } from "@/lib/chat-session";
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/types/api";

interface SessionListItemProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
  onRename: (sessionId: string, title: string) => void;
  onDelete: (sessionId: string) => void;
}

/** ⋯ menu (+ right click) — rename / delete conversation. */
export function SessionListItem({
  session,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: SessionListItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const displayTitle = sessionListTitle(session);
  const [titleDraft, setTitleDraft] = useState(displayTitle);

  function openRename() {
    setTitleDraft(displayTitle);
    setRenameOpen(true);
    setMenuOpen(false);
  }

  function confirmRename() {
    const trimmed = titleDraft.trim();
    if (trimmed) onRename(session.id, trimmed);
    setRenameOpen(false);
  }

  function confirmDelete() {
    onDelete(session.id);
    setDeleteOpen(false);
    setMenuOpen(false);
  }

  return (
    <>
      <div
        className={cn(
          "group flex items-stretch gap-0.5 rounded-md transition-colors hover:bg-accent",
          isActive && "bg-accent text-accent-foreground"
        )}
        onContextMenu={(e) => {
          e.preventDefault();
          setMenuOpen(true);
        }}
      >
        <button type="button" onClick={onSelect} className="min-w-0 flex-1 px-2 py-2 text-left">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-sm">{displayTitle}</span>
            {session.session_type === "general" ? (
              <span className="shrink-0 rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-medium">
                Auto
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {format(new Date(session.updated_at), "d MMM, HH:mm", { locale: pl })}
          </div>
        </button>
        <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-auto shrink-0 self-center opacity-70 group-hover:opacity-100"
              aria-label="Akcje rozmowy"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={openRename}>
              <Pencil className="mr-2 h-4 w-4" /> Zmień tytuł
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => {
                setDeleteOpen(true);
                setMenuOpen(false);
              }}
            >
              <Trash2 className="mr-2 h-4 w-4" /> Usuń rozmowę
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Tytuł rozmowy</DialogTitle>
          </DialogHeader>
          <Input
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            maxLength={200}
            onKeyDown={(e) => {
              if (e.key === "Enter") confirmRename();
            }}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRenameOpen(false)}>
              Anuluj
            </Button>
            <Button type="button" onClick={confirmRename}>
              Zapisz
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Usunąć rozmowę?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            „{displayTitle}” i cała historia zostaną trwale usunięte.
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteOpen(false)}>
              Anuluj
            </Button>
            <Button type="button" variant="destructive" onClick={confirmDelete}>
              Usuń
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
