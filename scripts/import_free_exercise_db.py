"""One-off import of exercises from yuhonas/free-exercise-db (Unlicense) into the goat catalog.

SQL-seed generator — it NEVER connects to the database. It produces
`supabase/migrations/0013_exercise_catalog_seed_free_exercise_db.sql`
(idempotent: `ON CONFLICT (slug) DO NOTHING`; manual entries `source='manual'` untouched).

Steps:
  1. Download `dist/exercises.json` from the pinned dataset commit SHA (cache in `.tmp/`).
  2. Offline transform: skip records without `instructions`, map fields (plan §2),
     categories/muscles EN→PL via the dictionaries below, deterministic sort by slug.
  3. (`--upload-photos`) Upload the first photo of each exercise to the Supabase Storage
     bucket `exercise-photos` — httpx + Storage REST, keys only from env:
       SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
     No supabase-py (per backend rule). Without this flag the script needs no secrets.
  4. SQL generation: chunked multi-row INSERTs; `photo_path` = bucket path
     (`free-exercise-db/<Id>/0.jpg`), not the project's full URL.

Re-import (refresh content from a newer dataset version):
    DELETE FROM exercises WHERE source = 'free_exercise_db';
    -- then rerun the generated file (SQL Editor / psql).

Usage:
    uv run python ../scripts/import_free_exercise_db.py            # SQL only
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
# Dataset version pin — re-import with a different SHA = different content; change deliberately (see plan).
SOURCE_COMMIT_SHA = "b0eed061e1c832b3ed815fbaa4b45b3cdc14df49"

BUCKET = "exercise-photos"
STORAGE_PREFIX = "free-exercise-db"  # <prefix>/<Id>/0.jpg in the bucket
LOCAL_PHOTO_DIRS = (
    CACHE_DIR / "exercise-photos-upload2" / STORAGE_PREFIX,
    CACHE_DIR / "exercise-photos-upload" / STORAGE_PREFIX,
)
CHUNK_SIZE = 100

LEVEL_MAP = {"beginner": "beginner", "intermediate": "intermediate", "expert": "advanced"}

# EN→PL dictionary: 7 categories + 17 primaryMuscles (full coverage of the dataset, measured 2026-08-23).
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
    """`Barbell_Squat` -> `barbell-squat` (dataset id is [A-Za-z0-9_ -], so this is enough)."""
    normalized = unicodedata.normalize("NFKD", source_id)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    if not slug:
        raise ValueError(f"Could not slugify id: {source_id!r}")
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
    print(f"[downloading] {url}")
    response = client.get(url, timeout=120)
    response.raise_for_status()
    data = response.json()
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def load_translations() -> dict[str, dict[str, object]]:
    """Cache from scripts/translate_exercises.py (if present) — otherwise seed stays EN."""
    path = CACHE_DIR / "free-exercise-db-translations.json"
    if path.exists():
        data: dict[str, dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
        complete = {k: v for k, v in data.items() if v.get("done")}
        print(f"[translations] {len(complete)} entries from cache")
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
                # PL from LLM when a translation is in cache; otherwise EN (catalog still works,
                # name_en always holds the original for plan-link matchers).
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
    """Fills missing variables from backend/.env — does not override already-set env."""
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
        sys.exit(f"Failed to create bucket {BUCKET}: {created.status_code} {created.text}")
    print(f"[photos] created public bucket {BUCKET}")


def upload_photos(rows: list[dict[str, object]], client: httpx.Client) -> None:
    load_backend_env()
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_key:
        sys.exit(
            "--upload-photos: env / backend/.env is missing SUPABASE_URL or "
            "SUPABASE_SERVICE_ROLE_KEY. Local mode (email/password) doesn't need them, "
            "but Storage does. Add both from the Supabase dashboard (Project Settings → API) "
            "and rerun — do not paste keys into the chat."
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
            sys.exit(f"Upload failed ({upload.status_code}) for {path}: {upload.text}")
        uploaded += 1
        if (uploaded + skipped) % 50 == 0:
            print(f"  ...{uploaded + skipped}/{len(rows)} (new {uploaded})")

    print(f"[photos] done: {uploaded} uploaded, {skipped} already present, {len(rows)} total")


def generate_sql(rows: list[dict[str, object]]) -> str:
    header = f"""-- Generated seed: import of free-exercise-db ({SOURCE_REPO}, Unlicense).
-- Generator: scripts/import_free_exercise_db.py; dataset SHA pin: {SOURCE_COMMIT_SHA}
-- DO NOT EDIT BY HAND — content is regeneratable (re-import: DELETE WHERE source='free_exercise_db', then rerun).
-- Run after 0012_exercise_catalog_source_nullable.sql. Idempotent (ON CONFLICT DO NOTHING);
-- manually curated entries (source='manual') remain untouched.
-- photo_path = path inside the exercise-photos bucket (not a full URL — API/FE compose the public address).

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
        help="Upload photos to Supabase Storage (keys from env or backend/.env).",
    )
    parser.add_argument(
        "--skip-sql",
        action="store_true",
        help="Don't overwrite migration 0013 (upload only / dry-run transform).",
    )
    args = parser.parse_args()

    with httpx.Client(follow_redirects=True) as client:
        raw = fetch_dataset(client)
        rows, skipped = transform(raw)  # type: ignore[arg-type]

        print(f"[transform] {len(rows)} exercises to import, skipped: {skipped or 'none'}")

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