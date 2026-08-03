# Coach — frontend

Vite + React + TypeScript + Tailwind + shadcn/ui (kod komponentów UI kopiowany ręcznie do
`src/components/ui/`, zgodnie z filozofią shadcn — to nie jest paczka npm).

Pełna architektura: [`docs/technical/frontend.md`](../docs/technical/frontend.md).

## Status

To jest **szkielet** (routing, layout, stores, klienci Supabase/API, strony-placeholdery).
Logika biznesowa (SSE chat streaming, formularz person, wykresy z realnymi danymi) — kolejne etapy.

## Wymagania

- Node.js 20+
- Dev project w Supabase Cloud (URL + anon key) — patrz [`../docs/technical/local-setup.md`](../docs/technical/local-setup.md)
- Uruchomiony lokalnie backend (domyślnie `http://localhost:8000`) — opcjonalnie na start, część ekranów
  (np. logowanie) działa bez niego

## Instalacja i uruchomienie lokalne

```bash
cd frontend
npm install
cp .env.example .env.local
# uzupełnij VITE_SUPABASE_URL i VITE_SUPABASE_ANON_KEY w .env.local
npm run dev
```

Aplikacja wystartuje pod `http://localhost:3000`.

## Skrypty

| Skrypt | Opis |
|---|---|
| `npm run dev` | Serwer deweloperski (Vite, HMR) |
| `npm run build` | Sprawdzenie typów (`tsc -b`) + build produkcyjny |
| `npm run preview` | Podgląd builda produkcyjnego |
| `npm run lint` | ESLint |
| `npm run test` | Testy jednostkowe (Vitest + React Testing Library) |

## Zmienne środowiskowe

Patrz [`.env.example`](./.env.example). Wszystkie zmienne muszą mieć prefiks `VITE_`, żeby Vite
wystawił je do kodu klienckiego.

## Struktura

```
src/
├── components/
│   ├── ui/        # shadcn/ui — kod kopiowany ręcznie (button, card, input, textarea, sheet...)
│   └── layout/    # AppShell (app shell dla tras chronionych)
├── lib/           # supabase.ts, api-client.ts, utils.ts (cn helper)
├── pages/         # strony routowane w App.tsx
├── store/         # zustand — stan kliencki/UI (patrz frontend.md #2)
├── types/         # typy API (docelowo generowane z /openapi.json)
└── App.tsx / main.tsx
```
