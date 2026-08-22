# Design: Widoczność konsultacji Goata (odpowiedzi trenerów w `consult_persona`)

**Data:** 2026-08-22
**Status:** proponowane (do implementacji)
**Bazuje na:** [2026-08-16-goat-consult-persona-design.md](./2026-08-16-goat-consult-persona-design.md), [team-lead.md](../../technical/team-lead.md)

## Problem

Gdy Goat woła `consult_persona`, user widzi tylko status w tle ("Goat konsultuje z {trener}…") i finalną syntezę Goata. Pełna odpowiedź trenera (`answer` w tool response) istnieje — jest nawet zapisywana do bazy (`insert_tool_message`, `role='tool'`) — ale nigdzie nie jest pokazywana userowi: FE jawnie filtruje `role='tool'` (`frontend/src/lib/chat-messages.ts:12`, test `chat-messages.test.ts:19` "ukrywa role=tool").

User chce móc **podejrzeć**, co realnie odpowiedział skonsultowany trener, zamiast polegać wyłącznie na syntezie Goata.

## Cel / zakres

Dodać **opcjonalny, domyślnie zwinięty** panel pod wiadomością Goata: "Zobacz co odpowiedział {trener}" — per konsultacja, w kolejności wywołań. Dotyczy to:

1. **Live** — konsultacje wykonane w bieżącej turze (SSE).
2. **Historia** — konsultacje z poprzednich tur, po przeładowaniu/otwarciu sesji `general` (`GET /chat/sessions/{id}/messages`).

**Nie zmieniamy** fundamentu ADR-17: Goat pozostaje jedynym "mówcą" domyślnie widocznym; trener nadal nie ma własnej bąbelkowej wiadomości z awatarem jako aktywny uczestnik rozmowy. To, co dodajemy, to **transparentność na żądanie** (rozwijany szczegół), nie zmiana modelu "kto mówi".

## Wymagania (Given / When / Then)

### GWT-1 — konsultacja w bieżącej turze jest widoczna po rozwinięciu

**Given** Goat w trakcie tury woła `consult_persona(slug, question)`
**When** trener zwróci odpowiedź (`status: "ok"`)
**Then** pod finalną wiadomością Goata pojawia się rozwijany element z etykietą trenera (`persona_label`), domyślnie **zwinięty**
**And** po rozwinięciu user widzi zarówno **pytanie**, które Goat zadał trenerowi, jak i **pełną odpowiedź** trenera
**And** element nie wygląda jak osobna wiadomość trenera (bez awatara/nagłówka persony jako "mówcy") — to załącznik do wiadomości Goata

### GWT-2 — wiele konsultacji w jednej turze (roundtable)

**Given** Goat konsultuje kilku trenerów w tej samej turze (np. "niech każdy się wypowie")
**When** tura się kończy
**Then** pod wiadomością Goata pojawia się **lista** rozwijanych elementów, jeden per konsultacja, w kolejności wywołań
**And** każdy ma własną etykietę trenera i własne pytanie/odpowiedź

### GWT-3 — błąd konsultacji nie tworzy załącznika

**Given** `consult_persona` zwraca `{"error": ...}` (zły slug, timeout, limit)
**When** tura się kończy
**Then** **nie** pojawia się rozwijany element (błąd nadal widoczny wyłącznie jako dotychczasowy chip `tool_result` / komunikat Goata)

### GWT-4 — historia sesji po przeładowaniu

**Given** user otwiera ponownie sesję `general` z wcześniejszymi konsultacjami
**When** FE pobiera `GET /chat/sessions/{id}/messages`
**Then** wiadomości Goata, po których nastąpiła udana konsultacja, mają ten sam rozwijany element co w trybie live (identyczny content: pytanie + odpowiedź + etykieta)
**And** kolejność i przypisanie do właściwej wiadomości Goata jest zachowane (parowanie po `tool_call_id`)

### GWT-5 — slash / sesja 1:1 bez zmian

**Given** wiadomość `/slug` lub sesja `persona`
**When** tura się wykonuje
**Then** brak konsultacji, brak nowego elementu UI (funkcja dotyczy wyłącznie ścieżki Goat + `consult_persona`)

## Architektura

### Backend — zmiana 1: `question` w tool response `consult_persona`

`backend/app/domain/chat/orchestrator.py`, `_consult_persona` (~linia 848-857) już zna `question` (rozpakowane z argumentów), ale nie wkłada go do zwracanego JSON-a. Dodać pole `question`, żeby persystowany `tool` message (i SSE event, patrz niżej) niósł komplet danych bez konieczności odczytywania osobno `tool_calls.arguments` z poprzedzającej wiadomości `assistant`:

```python
return json.dumps(
    {
        "status": "ok",
        "slug": target.slug,
        "persona_label": label,
        "question": question,      # NOWE
        "answer": answer.strip(),
    },
    ensure_ascii=False,
)
```

Bez zmian schematu DB — `chat_messages.content` to już `text`/`jsonb`-friendly pole, konsultacje są już persystowane (`insert_tool_message`, linia ~631-638).

### Backend — zmiana 2: nowy SSE event `consult_detail` (live)

Nie rozszerzać kontraktu `tool_result` (`_tool_result_event_payload`, `orchestrator.py:149`) — jego docstring jawnie mówi "kontrakt FE (tool_name/summary/success) — nie surowy JSON tool response", to świadoma decyzja i inni konsumenci `tool_result` nie powinni dostawać nagle dużego tekstu. Zamiast tego, w `_consult_persona`, **obok** istniejącego `tool_result`, wyemitować dedykowany event tylko gdy `status == "ok"`:

```python
if user_queue is not None and ok:
    await _emit(
        user_queue,
        "consult_detail",
        {
            "tool_call_id": tool_call_id,   # przekazać przez sygnaturę _consult_persona
            "slug": target.slug,
            "persona_label": label,
            "question": question,
            "answer": answer.strip(),
        },
    )
```

Wymaga przekazania `tool_call_id` do `_consult_persona` (dziś zna go tylko `_run_single_tool`/pętla w `handle_message`, ~linia 599-610) — dociągnąć jako parametr.

Miejsce w strumieniu: **po** `tool_result` tej konsultacji, przed kontynuacją tokenów Goata (synteza) lub kolejną konsultacją.

### Backend — bez zmian

- Limit 5 konsultacji/turę — bez zmian.
- Persystencja — już działa (`role='tool'`), tylko FE dziś to ukrywa.
- Moderacja — odpowiedź trenera przechodzi ten sam pipeline co dziś (system prompt trenera + `safety_prompt`); nie dodajemy nowej ścieżki treści niezmoderowanej, bo Goat i tak już widzi ten tekst w kontekście (dziś tylko go syntetyzuje zamiast pokazywać 1:1).

### Frontend — SSE (live)

`frontend/src/types/chat-stream.ts` — nowy typ:

```ts
export interface ChatStreamConsultDetailEvent {
  type: "consult_detail";
  tool_call_id: string;
  slug: string;
  persona_label: string;
  question: string;
  answer: string;
}
```

Dodać do unii `ChatStreamEvent`.

`frontend/src/hooks/useChatTurnRunner.ts` — zbierać `consult_detail` eventy w buforze per-tura (np. `consultDetails: ChatStreamConsultDetailEvent[]`), analogicznie do akumulacji `tool_calls`/tokenów. Przy finalizacji wiadomości Goata (`done`) dołączyć zebraną listę do obiektu wiadomości w store (np. `message.consultDetails`), żeby `MessageBubble` miał do niej dostęp.

### Frontend — historia (reload)

`frontend/src/lib/chat-messages.ts` — dziś linia 12 odrzuca `role === "tool"` całkowicie. Zmiana: **nie** renderować `role='tool'` jako osobnej wiadomości (to się nie zmienia — nadal brak bąbelka trenera), ale **wyciągnąć** z tych wierszy dane konsultacji i doczepić do poprzedzającej wiadomości `assistant` (Goata) po `tool_call_id`:

1. Iterować wiadomości w kolejności.
2. Dla `role='assistant'` z `tool_calls` zawierającymi wywołanie `consult_persona` — zapamiętać `tool_call_id → assistant.id`.
3. Dla kolejnego `role='tool'` z tym `tool_call_id`, sparsować `content` jako JSON; jeśli ma `status: "ok"` i pole `answer` — zbudować wpis `{persona_label, question, answer}` i dopisać do `consultDetails` odpowiedniej wiadomości Goata z kroku 2.
4. Wiersze `role='tool'` nadal nie trafiają do listy renderowanych wiadomości (jak dziś).

Parsowanie odporne na błędy (`try/catch` → pomiń wpis, nie wywalaj całej historii) — ten sam wzorzec co reszta parsowania tool response na FE.

### Frontend — komponent UI

Nowy komponent, np. `frontend/src/components/chat/ConsultDetails.tsx`:

- Renderowany pod treścią `MessageBubble` **tylko** dla wiadomości Goata (`persona_id === null`) z niepustym `consultDetails`.
- Lista rozwijanych elementów (`<details>`/Radix Collapsible/Accordion — użyć istniejącego prymitywu z `components/ui`, jeśli jest w projekcie; sprawdzić `components/ui/accordion.tsx` lub podobne przed pisaniem od zera).
- Domyślnie **zwinięte**.
- Nagłówek: etykieta trenera (`persona_label`), np. "Bartek · Trener motoryczny odpowiedział".
- Po rozwinięciu: pytanie Goata (mniejszym/wyszarzonym tekstem, prefiks "Pytanie:") + odpowiedź trenera (główny tekst).
- Styl wizualnie odróżniony od `MessageBubble` (np. mniejsza czcionka, ramka, wcięcie) — to ma czytać się jako "podgląd źródła", nie jako kolejna wiadomość w rozmowie.

## Błędy

| Przypadek | Zachowanie |
|-----------|------------|
| `consult_persona` zwraca error | brak `consult_detail` (live) / brak wpisu w historii (parsowanie JSON bez `answer`) |
| Malformed JSON w `role='tool'` przy parsowaniu historii | pomiń wpis, nie przerywaj renderowania reszty historii |
| `consult_detail` przyjdzie bez odpowiadającego `tool_result`/wiadomości Goata (edge case przy przerwanym streamie) | FE ignoruje osierocony `consult_detail` (nie ma do czego doczepić) |

## Testy

- Backend: `_consult_persona` zwraca `question` w JSON (happy path).
- Backend: `consult_detail` event emitowany tylko przy `status: "ok"`, z poprawnym `tool_call_id`.
- Backend: brak `consult_detail` przy błędzie (zły slug / limit / timeout).
- FE: `chat-messages.ts` — parowanie `assistant.tool_calls` (`consult_persona`) ↔ `tool` po `tool_call_id`, zbudowanie `consultDetails`.
- FE: `chat-messages.ts` — malformed JSON w `role='tool'` nie wywala parsowania historii.
- FE: `useChatTurnRunner` — akumulacja `consult_detail` w trakcie streamu, dołączenie do finalnej wiadomości.
- FE: `ConsultDetails` — domyślnie zwinięte; rozwinięcie pokazuje pytanie + odpowiedź; nie renderuje się gdy `consultDetails` puste.
- FE: roundtable — 2+ konsultacje w jednej turze → 2+ elementy w poprawnej kolejności.

## Poza zakresem (tej iteracji)

- Zmiana treści/formatu odpowiedzi trenera pod kątem bezpośredniej czytelności dla usera (dziś `answer` jest pisane jako "brief dla Goata", nie jako user-facing copy — patrz "Otwarte pytanie" niżej).
- Możliwość odpowiedzi/dopytania trenera bezpośrednio z poziomu tego panelu (to już byłby krok w stronę pełnego multi-agent chatu, poza zakresem tej zmiany).
- Sesja `persona` (1:1) i slash — bez zmian, tam `consult_persona` nie występuje.
- Eksport/druk historii z uwzględnieniem konsultacji — nieadresowane.

## Otwarte pytanie (do decyzji przed/podczas implementacji)

`answer` trenera dziś jest generowany z myślą "to czyta Goat, nie user" (prompt trenera w `consult`-turze to zwykły `handle_message`, bez wiedzy że tekst może trafić bezpośrednio przed oczy usera). Po tej zmianie user może zobaczyć surowy tekst. Do rozstrzygnięcia:

- **Opcja A (rekomendowana na start):** nic nie zmieniać w prompcie trenera — to i tak ten sam tekst, na podstawie którego Goat już dziś buduje odpowiedź, więc nie jest to nowa "niekontrolowana" treść, tylko dotąd ukryta. Zaakceptować, że może brzmieć nieco "technicznie"/skrótowo jako podgląd źródła.
- **Opcja B:** dodać do prompta trenera w trybie `consult` notatkę w stylu "Twoja odpowiedź może być pokazana userowi jako podgląd — pisz zwięźle i zrozumiale" — koszt: dodatkowa gałąź w prompcie, ryzyko zmiany zachowania istniejącej ścieżki konsultacji (dziś zoptymalizowanej pod "brief dla Goata").

Nie blokuje implementacji UI — można wdrożyć z opcją A i ewentualnie przejść na B po obserwacji jakości tekstu w praniu.

## Dokumenty do aktualizacji przy wdrożeniu

- `docs/technical/team-lead.md` — nowa sekcja "Widoczność konsultacji" + aktualizacja diagramu SSE (fragment `## SSE`).
- `docs/technical/ai-pipeline.md` §1a — wzmianka o `consult_detail`.
- `docs/technical/architecture.md` §3a — dopisać `consult_detail` do listy eventów w "Frontend SSE eventy (kontrakt)".
- `docs/technical/frontend.md` — nowy komponent `ConsultDetails`, jeśli plik dokumentuje komponenty czatu.
