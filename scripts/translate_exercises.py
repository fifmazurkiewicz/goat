"""One-off offline translation of free-exercise-db exercises to Polish via OpenRouter.

Input: `.tmp/free-exercise-db-translations.json` (cache, created/resumed automatically).
Output: the same file enriched with `name_pl`, `short_pl`, `detail_pl`, `done`.

Rules:
- Batches of ~12 exercises, response as JSON (response_format json_object); each batch is
  written to the cache immediately — interrupting the script does not lose progress,
  rerun continues.
- Technical instructions: translate faithfully, do NOT add advice of your own
  (red flags / technique are the persona's domain; the catalog is just reference).
- Key: OPENROUTER_API_KEY from env; model: OPENROUTER_CHAT_MODEL (same as chat).

Usage (from backend/, app venv):
    uv run python ../scripts/translate_exercises.py            # full run + report
    uv run python ../scripts/translate_exercises.py --limit 20 # smoke on a sample
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".tmp"
TRANSLATIONS_PATH = CACHE_DIR / "free-exercise-db-translations.json"
DATASET_GLOB = "free-exercise-db-*.json"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
BATCH_SIZE = 12
RETRY_LIMIT = 4


def load_source_rows() -> list[dict[str, object]]:
    files = [
        f
        for f in sorted(CACHE_DIR.glob("free-exercise-db-*.json"))
        if "translations" not in f.name
    ]
    if not files:
        sys.exit(
            f"Brak cache datasetu ({CACHE_DIR / DATASET_GLOB}). "
            "Najpierw: uv run python ../scripts/import_free_exercise_db.py"
        )
    raw = json.loads(files[-1].read_text(encoding="utf-8"))

    rows: list[dict[str, object]] = []
    for item in raw:
        instructions = [s.strip() for s in item.get("instructions") or [] if s.strip()]
        if not str(item.get("name", "")).strip() or not instructions:
            continue
        rows.append({"id": str(item["id"]), "name": str(item["name"]), "instructions": instructions})
    return rows


def load_translations() -> dict[str, dict[str, object]]:
    if TRANSLATIONS_PATH.exists():
        return json.loads(TRANSLATIONS_PATH.read_text(encoding="utf-8"))
    return {}


def save_translations(data: dict[str, dict[str, object]]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    TRANSLATIONS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def build_prompt(batch: list[dict[str, object]]) -> str:
    payload = json.dumps(
        [{"id": b["id"], "name": b["name"], "instructions": b["instructions"]} for b in batch],
        ensure_ascii=False,
    )
    return f"""Przetłumacz poniższe ćwiczenia siłowe/cardio z angielskiego na polski.

Zasady:
- "name_pl": naturalna polska nazwa ćwiczenia używana na siłowni (np. "Barbell Squat" → "Przysiad ze sztangą", "Bench Press" → "Wyciskanie sztangi leżąc"). Nie dosłownie.
- "short_pl": krótki opis 2–3 zdań: co to za ćwiczenie i jak je wykonać w skrócie. Prosty język, bez lania wody.
- "detail_pl": instrukcja krok po kroku — przetłumacz WSZYSTKIE kroki wiernie, zachowaj kolejność i liczbę kroków, każdy krok jako osobny element listy "steps". Tylko tłumaczenie — NIE dodawaj własnych rad, ostrzeżeń ani kroków, których nie ma w oryginale.
- Terminologia fitness: "reps" → "powtórzenia", "core" → "mięśnie głębokie", "starting position" → "pozycja startowa".

Odpowiedz WYŁĄCZNIE obiektem JSON:
{{"exercises": [{{"id": "...", "name_pl": "...", "short_pl": "...", "detail_pl": {{"steps": ["...", "..."]}}}}]}}

Ćwiczenia do tłumaczenia:
{payload}"""


def translate_batch(client: httpx.Client, model: str, batch: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    # Key from app configuration (pydantic-settings reads backend/.env) — this script
    # NEVER opens .env or prints secret values.
    from app.core.config import settings as app_settings

    api_key = app_settings.openrouter_api_key.get_secret_value()
    if not api_key:
        sys.exit("OPENROUTER_API_KEY brak w konfiguracji (backend/.env — patrz .env.example).")

    response = client.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "Jesteś precyzyjnym tłumaczem treści fitness EN→PL. Zwracasz wyłącznie poprawny JSON.",
                },
                {"role": "user", "content": build_prompt(batch)},
            ],
        },
        timeout=180,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    parsed = json.loads(content)
    out: dict[str, dict[str, object]] = {}
    source_ids = {str(b["id"]) for b in batch}
    for entry in parsed.get("exercises", []):
        exercise_id = str(entry.get("id", ""))
        steps = entry.get("detail_pl", {}).get("steps", [])
        name_pl = str(entry.get("name_pl", "")).strip()
        short_pl = str(entry.get("short_pl", "")).strip()
        if not (exercise_id in source_ids and name_pl and short_pl and steps):
            continue
        out[exercise_id] = {
            "name_pl": name_pl,
            "short_pl": short_pl,
            "detail_pl": "\n".join(f"{i}. {str(s).strip()}" for i, s in enumerate(steps, start=1)),
            "done": True,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Policz tylko pierwsze N nieprzetłumaczonych (smoke).")
    args = parser.parse_args()

    model = os.environ.get("OPENROUTER_CHAT_MODEL", "").strip() or "x-ai/grok-4-fast"
    source_rows = load_source_rows()
    translations = load_translations()
    already = sum(1 for row in source_rows if str(row["id"]) in translations)
    pending = [row for row in source_rows if str(row["id"]) not in translations]
    if args.limit:
        pending = pending[: args.limit]

    total = len(source_rows)
    print(f"[stan] {already}/{total} gotowe, do przetłumaczenia teraz: {len(pending)} (model: {model})")

    done_now = 0
    with httpx.Client() as client:
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start : start + BATCH_SIZE]
            for attempt in range(1, RETRY_LIMIT + 1):
                try:
                    results = translate_batch(client, model, batch)
                    break
                except Exception as exc:  # noqa: BLE001 — retry on any API/deserialize error
                    wait = attempt * 15
                    print(f"  [retry] batch od #{start}: {exc} — ponawiam za {wait}s ({attempt}/{RETRY_LIMIT})")
                    time.sleep(wait)
                    results = {}

            translations.update(results)
            save_translations(translations)
            done_now += len(results)
            missing = len(batch) - len(results)
            note = f" (BRAKI: {missing})" if missing else ""
            print(f"[batch {start + len(batch)}/{len(pending)}] zapisano, łącznie {already + done_now}/{total}{note}")

    still_missing = [r["id"] for r in source_rows if str(r["id"]) not in translations]
    if still_missing:
        print(f"[koniec] BRAKUJE {len(still_missing)}: {still_missing[:10]}")
        sys.exit(1)
    print("[koniec] komplet tłumaczeń.")


if __name__ == "__main__":
    main()