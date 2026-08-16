# Plan: mobile layout (Android / iOS) — 2026-08-16

## Problem

Na telefonach historia czatu nie była widoczna od razu. Pozostałe ekrany: za duży gutter, brak safe area, touch < 44px.

## Decyzje

| Data | Decyzja | Dlaczego |
|------|---------|----------|
| 2026-08-16 | Wariant A: zamek viewportu czatu (`dvh` + visualViewport, `main overflow-hidden` tylko na `/chat`, pin historii na dół) | Leczy zgłoszony bug bez zmiany IA |
| 2026-08-16 | Bez wirtualizacji MessageList w MVP | `estimateSize: 88` psuło first paint |
| 2026-08-16 | Bottom nav odłożony | Świadoma zmiana IA; nie mieszać z hotfixem wysokości |
| 2026-08-16 | Safe area + `PAGE_SHELL_CLASS` na pozostałych stronach | Jedna zmiana layoutu naprawia wiele ekranów |
| 2026-08-16 | `useIsMobile` = szerokość &lt;768 **lub** wysokość &lt;500 | iPhone landscape nie dostaje desktopowego Dialogu / siatki miesiąca |
| 2026-08-16 | Input/textarea `text-base` na mobile | Safari nie zoomuje przy focusie (font ≥16px) |
| 2026-08-16 | `ResponsiveDialog`: jeden scroll, footer shrink-0 + safe area | Klawiatura nie chowa Zapisz |

## Given / When / Then

- Given otwarta sesja z historią na telefonie, When user wchodzi na `/chat/:id`, Then ostatnie wiadomości są w kadrze, pole Wyślij widoczne.
- Given klawiatura iOS/Android, When user focusuje composer, Then layout kurczy się z visualViewport, historia zostaje nad klawiaturą.
- Given `/plans` / `/results` / `/personas` / `/profile` / `/settings`, When user scrolluje, Then treść nie jest obcięta przez home indicator.
- Given iPhone landscape, When user otwiera formularz persony, Then widzi Sheet (nie wyśrodkowany Dialog).
- Given focus w polu czatu na iOS, When pojawia się klawiatura, Then strona nie zoomuje (font ≥16px).
