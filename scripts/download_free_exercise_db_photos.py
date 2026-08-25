"""Download all free-exercise-db exercise photos (0.jpg + 1.jpg) to a local cache.

Source: yuhonas/free-exercise-db (Unlicense), same commit pin as
`scripts/import_free_exercise_db.py`.

Output layout (matches import LOCAL_PHOTO_DIRS):
  .tmp/exercise-photos-upload/free-exercise-db/<Id>/0.jpg
  .tmp/exercise-photos-upload/free-exercise-db/<Id>/1.jpg

Skips files that already exist and are non-empty. Does not touch Supabase —
upload with:
  cd backend
  uv run python ../scripts/import_free_exercise_db.py --upload-photos --skip-sql

Usage:
  uv run python scripts/download_free_exercise_db_photos.py
  uv run python scripts/download_free_exercise_db_photos.py --workers 16
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".tmp"
OUT_ROOT = CACHE_DIR / "exercise-photos-upload" / "free-exercise-db"

SOURCE_REPO = "yuhonas/free-exercise-db"
SOURCE_COMMIT_SHA = "b0eed061e1c832b3ed815fbaa4b45b3cdc14df49"
RAW_BASE = (
    f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT_SHA}/exercises"
)

# Same skip list as import transform (no instructions → not in catalog).
SKIP_IDS = frozenset(
    {
        "Iron_Cross",
        "One-Arm_Kettlebell_Swings",
        "Push_Press",
        "Side_Bridge",
        "Side_Jackknife",
    }
)


def fetch_dataset(client: httpx.Client) -> list[dict[str, object]]:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"free-exercise-db-{SOURCE_COMMIT_SHA[:10]}.json"
    if cache_file.exists():
        print(f"[cache] {cache_file}")
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        url = (
            f"https://raw.githubusercontent.com/{SOURCE_REPO}/"
            f"{SOURCE_COMMIT_SHA}/dist/exercises.json"
        )
        print(f"[downloading] {url}")
        response = client.get(url, timeout=120)
        response.raise_for_status()
        cache_file.write_text(response.text, encoding="utf-8")
        data = response.json()
    if not isinstance(data, list):
        sys.exit("Expected exercises.json to be a list")
    return data  # type: ignore[return-value]


def exercise_ids(raw: list[dict[str, object]]) -> list[str]:
    ids: list[str] = []
    for item in raw:
        source_id = str(item["id"])
        if source_id in SKIP_IDS:
            continue
        instructions = item.get("instructions") or []
        if not instructions:
            continue
        ids.append(source_id)
    ids.sort()
    return ids


def download_one(
    client: httpx.Client,
    source_id: str,
    filename: str,
) -> str:
    """Returns status: 'ok' | 'skip' | 'fail'."""
    dest = OUT_ROOT / source_id / filename
    if dest.is_file() and dest.stat().st_size > 0:
        return "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{RAW_BASE}/{source_id}/{filename}"
    try:
        response = client.get(url, timeout=60)
        response.raise_for_status()
        dest.write_bytes(response.content)
        return "ok"
    except Exception as exc:  # noqa: BLE001 — collect failures, keep going
        print(f"[fail] {source_id}/{filename}: {exc}", file=sys.stderr)
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
        return "fail"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Parallel HTTP downloads (default 12).",
    )
    args = parser.parse_args()
    workers = max(1, min(args.workers, 32))

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        raw = fetch_dataset(client)
        ids = exercise_ids(raw)
        jobs = [(sid, name) for sid in ids for name in ("0.jpg", "1.jpg")]
        print(f"[plan] {len(ids)} exercises x 2 = {len(jobs)} files -> {OUT_ROOT}")

        ok = skip = fail = 0
        # Thread-local clients: share one client is ok for httpx with threads if careful;
        # create per-task requests via a pool of clients is heavier — use one Client
        # with limits (httpx is thread-safe for requests in recent versions).
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(download_one, client, sid, name): (sid, name)
                for sid, name in jobs
            }
            done = 0
            for future in as_completed(futures):
                status = future.result()
                if status == "ok":
                    ok += 1
                elif status == "skip":
                    skip += 1
                else:
                    fail += 1
                done += 1
                if done % 100 == 0 or done == len(jobs):
                    print(f"  ...{done}/{len(jobs)} (new {ok}, skip {skip}, fail {fail})")

    print(f"[done] new={ok} skipped={skip} failed={fail} total={len(jobs)}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
