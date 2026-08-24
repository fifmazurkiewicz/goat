"""Jednorazowy import ćwiczeń z yuhonas/free-exercise-db (Unlicense) do katalogu goat.

Generator SQL-seeda — NIGDY nie łączy się z bazą. Produkuje
`supabase/migrations/0013_exercise_catalog_seed_free_exercise_db.sql`
(idempotentny: `ON CONFLICT (slug) DO NOTHING`; ręczne wpisy `source='manual'` nietykalne).

Kroki:
  1. Pobranie `dist/exercises.json` z przypiętego SHA commitu datasetu (cache w `.tmp/`).
  2. Transform offline: skip rekordów bez `instructions`, mapowanie pól (plan §2),
     kategorie/mięśnie EN→PL ze słownika poniżej, deterministyczny sort po slug.
  3. (`--upload-photos`) Upload pierwszego zdjęcia każdego ćwiczenia do Supabase Storage
     bucket `exercise-photos` — httpx + Storage REST, klucze wyłącznie z env:
       SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
     Bez supabase-py (zgodnie z regułą backendu). Bez tej flagi skrypt nie potrzebuje
     żadnych sekretów.
  4. Generacja SQL: chunkowane multi-row INSERT-y; `photo_path` = ścieżka w buckecie
     (`free-exercise-db/<Id>/0.jpg`), nie pełny URL projektu.

Re-import (odświeżenie treści z nowszej wersji datasetu):
    DELETE FROM exercises WHERE source = 'free_exercise_db';
    -- potem ponowne uruchomienie wygenerowanego pliku (SQL Editor / psql).

Użycie:
    uv run python ../scripts/import_free_exercise_db.py            # tylko generacja SQL
    uv run python ../scripts/import_free_exercise_db.py --upload-photos
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".tmp"
OUTPUT_PATH = (
    REPO_ROOT / "supabase" / "migrations" / "0013_exercise_catalog_seed_free_exercise_db.sql"
)

SOURCE_REPO = "yuhonas/free-exercise-db"
# Pin wersji datasetu — re-import z innym SHA = inna treść; zmieniaj świadomie (patrz plan).
SOURCE_COMMIT_SHA = "b0eed061e1c832b3ed815fbaa4b45b3cdc14df49"

BUCKET = "exercise-photos"
STORAGE_PREFIX = "free-exercise-db"  # <prefix>/<Id>/0.jpg w buckecie
LOCAL_PHOTO_DIRS = (
    CACHE_DIR / "exercise-photos-upload2" / STORAGE_PREFIX,
    CACHE_DIR / "exercise-photos-upload" / STORAGE_PREFIX,
)
CHUNK_SIZE = 100

LEVEL_MAP = {"beginner": "beginner", "intermediate": "intermediate", "expert": "advanced"}

# Słownik EN→PL: 7 category + 17 primaryMuscles (pełne pokrycie datasetu, pomiar 2026-08-23).
CATEGORY_PL = {
    "strength": "Siłowe",
    "stretching": "Rozciąganie",
    "plyometrics": "Plyometryka",
    "powerlifting": "Trójbój",
    "olympic weightlifting": "Podnoszenie ciężarów",
    "strongman": "Strongman",
    "cardio": "Cardio",
}

MUSCLE_PL = {
    "quadriceps": "Uda",
    "shoulders": "Barki",
    "abdominals": "Brzuch",
    "chest": "Klatka piersiowa",
    "hamstrings": "Dwugłowe uda",
    "triceps": "Triceps",
    "biceps": "Biceps",
    "lats": "Najszersze grzbietu",
    "middle back": "Środek pleców",
    "calves": "Łydki",
    "lower back": "Dolny odcinek pleców",
    "forearms": "Przedramiona",
    "glutes": "Pośladki",
    "traps": "Czworoboczne",
    "adductors": "Przywodziciele",
    "neck": "Kark",
    "abductors": "Odwodziciele",
}


def slugify(source_id: str) -> str:
    """`Barbell_Squat` -> `barbell-squat` (id datasetu jest [A-Za-z0-9_ -], więc wystarczy)."""
    normalized = unicodedata.normalize("NFKD", source_id)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    if not slug:
        raise ValueError(f"Nie udało się slugify id: {source_id!r}")
    return slug


def sql_literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def sql_text_array(values: list[str]) -> str:
    inner = ", ".join(sql_literal(v) for v in values)
    return f"array[{inner}]"


def fetch_dataset(client: httpx.Client) -> dict[str, object]:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"free-exercise-db-{SOURCE_COMMIT_SHA[:10]}.json"
    if cache_file.exists():
        print(f"[cache] {cache_file}")
        return json.loads(cache_file.read_text(encoding="utf-8"))

    url = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT_SHA}/dist/exercises.json"
    print(f"[pobieram] {url}")
    response = client.get(url, timeout=120)
    response.raise_for_status()
    data = response.json()
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def load_translations() -> dict[str, dict[str, object]]:
    """Cache z scripts/translate_exercises.py (jeśli jest) — inaczej seed zostaje po EN."""
    path = CACHE_DIR / "free-exercise-db-translations.json"
    if path.exists():
        data: dict[str, dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
        complete = {k: v for k, v in data.items() if v.get("done")}
        print(f"[tłumaczenia] {len(complete)} pozycji z cache")
        return complete
    return []


def transform(raw: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str]]:
    skipped: list[str] = []
    translations = load_translations()
    rows: list[dict[str, object]] = []
    for item in raw:
        name = str(item["name"]).strip()
        instructions = [step.strip() for step in item.get("instructions") or [] if step.strip()]
        if not name or not instructions:
            skipped.append(str(item["id"]))
            continue

        source_id = str(item["id"])
        categories_raw = ([item.get("category")] if item.get("category") else []) + list(
            item.get("primaryMuscles") or []
        )
        seen: set[str] = set()
        categories: list[str] = []
        for value in categories_raw:
            translated = CATEGORY_PL.get(str(value), MUSCLE_PL.get(str(value), str(value)))
            if translated not in seen:
                seen.add(translated)
                categories.append(translated)

        numbered = "\n".join(f"{i}. {step}" for i, step in enumerate(instructions, start=1))
        translation = translations.get(source_id)
        rows.append(
            {
                "slug": slugify(source_id),
                # PL z LLM gdy tłumaczenie jest w cache; inaczej EN (katalog nadal działa,
                # name_en zawsze trzyma oryginał dla matcherów linków z planów).
                "name": str(translation["name_pl"]) if translation else name,
                "name_en": name,
                "level": LEVEL_MAP[str(item["level"])],
                "categories": categories,
                "short_description": (
                    str(translation["short_pl"]) if translation else instructions[0]
                ),
                "detail_full": (
                    str(translation["detail_pl"]) if translation else numbered
                ),
                "storage_path": f"{STORAGE_PREFIX}/{source_id}/0.jpg",
            }
        )
    rows.sort(key=lambda r: str(r["slug"]))
    return rows, skipped


def load_backend_env() -> None:
    """Uzupełnia brakujące zmienne z backend/.env — nie nadpisuje już ustawionego env."""
    env_path = REPO_ROOT / "backend" / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def local_photo_bytes(source_id: str) -> bytes | None:
    for root in LOCAL_PHOTO_DIRS:
        candidate = root / source_id / "0.jpg"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate.read_bytes()
    return None


def ensure_public_bucket(client: httpx.Client, supabase_url: str, headers: dict[str, str]) -> None:
    listed = client.get(f"{supabase_url}/storage/v1/bucket/{BUCKET}", headers=headers, timeout=30)
    if listed.status_code == 200:
        return
    created = client.post(
        f"{supabase_url}/storage/v1/bucket",
        headers={**headers, "Content-Type": "application/json"},
        json={"id": BUCKET, "name": BUCKET, "public": True, "file_size_limit": 5_000_000},
        timeout=30,
    )
    if created.status_code not in (200, 201):
        sys.exit(f"Nie udało się utworzyć bucketa {BUCKET}: {created.status_code} {created.text}")
    print(f"[zdjęcia] utworzono publiczny bucket {BUCKET}")


def upload_photos(rows: list[dict[str, object]], client: httpx.Client) -> None:
    load_backend_env()
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_key:
        sys.exit(
            "--upload-photos: w env / backend/.env brak SUPABASE_URL albo "
            "SUPABASE_SERVICE_ROLE_KEY. Lokalny tryb (email/hasło) ich nie potrzebuje, "
            "ale Storage tak. Dopisz obie z dashboardu Supabase (Project Settings → API) "
            "i odpal ponownie — nie wklejaj kluczy do czatu."
        )

    auth_headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
    }
    ensure_public_bucket(client, supabase_url, auth_headers)

    uploaded = skipped = 0
    for row in rows:
        path = str(row["storage_path"])
        head = client.get(
            f"{supabase_url}/storage/v1/object/public/{BUCKET}/{path}",
            headers={"Range": "bytes=0-0"},
            timeout=30,
        )
        if head.status_code in (200, 206):
            skipped += 1
            continue

        source_id_dir = path.split("/")[1]
        content = local_photo_bytes(source_id_dir)
        if content is None:
            image_url = (
                f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT_SHA}"
                f"/exercises/{source_id_dir}/0.jpg"
            )
            image = client.get(image_url, timeout=60)
            image.raise_for_status()
            content = image.content

        upload = client.post(
            f"{supabase_url}/storage/v1/object/{BUCKET}/{path}",
            headers={
                **auth_headers,
                "Content-Type": "image/jpeg",
                "x-upsert": "true",
            },
            content=content,
            timeout=120,
        )
        if upload.status_code not in (200, 201):
            sys.exit(f"Upload nieudany ({upload.status_code}) dla {path}: {upload.text}")
        uploaded += 1
        if (uploaded + skipped) % 50 == 0:
            print(f"  ...{uploaded + skipped}/{len(rows)} (nowe {uploaded})")

    print(f"[zdjęcia] gotowe: {uploaded} wgranych, {skipped} już było, łącznie {len(rows)}")


def generate_sql(rows: list[dict[str, object]]) -> str:
    header = f"""-- Wygenerowany seed: import free-exercise-db ({SOURCE_REPO}, Unlicense).
-- Generator: scripts/import_free_exercise_db.py; pin SHA datasetu: {SOURCE_COMMIT_SHA}
-- NIE EDYTUJ RĘCZNIE — treść regenerowalna (re-import: DELETE WHERE source='free_exercise_db', potem rerun).
-- Uruchomić po 0012_exercise_catalog_source_nullable.sql. Idempotentny (ON CONFLICT DO NOTHING);
-- ręcznie kuratorowane wpisy (source='manual') pozostają nietknięte.
-- photo_path = ścieżka w buckecie exercise-photos (nie pełny URL — API/FE składa publiczny adres).

insert into public.exercises
  (slug, name, name_en, persona_type, level, categories, short_description, detail_full, common_mistakes, photo_path, source)
values
"""

    chunks: list[str] = []
    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        values = []
        for row in chunk:
            photo_path = str(row["storage_path"])
            values.append(
                "  ({}, {}, {}, 'motor_coach', {}, {}, {}, {}, NULL, {}, 'free_exercise_db')".format(
                    sql_literal(str(row["slug"])),
                    sql_literal(str(row["name"])),
                    sql_literal(row.get("name_en")),  # type: ignore[arg-type]
                    sql_literal(str(row["level"])),
                    sql_text_array(list(row["categories"])),  # type: ignore[arg-type]
                    sql_literal(str(row["short_description"])),
                    sql_literal(str(row["detail_full"])),
                    sql_literal(photo_path),
                )
            )
        chunks.append(header + ",\n".join(values) + f"\non conflict (slug) do nothing;\n")

    return "\n".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upload-photos",
        action="store_true",
        help="Upload zdjęć do Supabase Storage (klucze z env albo backend/.env).",
    )
    parser.add_argument(
        "--skip-sql",
        action="store_true",
        help="Nie nadpisuj migracji 0013 (sam upload / dry-run transform).",
    )
    args = parser.parse_args()

    with httpx.Client(follow_redirects=True) as client:
        raw = fetch_dataset(client)
        rows, skipped = transform(raw)  # type: ignore[arg-type]

        print(f"[transform] {len(rows)} ćwiczeń do importu, pominięte: {skipped or 'brak'}")

        if args.upload_photos:
            upload_photos(rows, client)

        if args.skip_sql:
            return

        sql = generate_sql(rows)

    OUTPUT_PATH.write_text(sql, encoding="utf-8", newline="\n")
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"[sql] {OUTPUT_PATH.relative_to(REPO_ROOT)} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
