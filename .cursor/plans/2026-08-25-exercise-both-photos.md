# Both free-exercise-db photos (0.jpg + 1.jpg)

**Goal:** Download and serve both dataset photos per exercise.

**Architecture:** Keep `photo_path` = `…/0.jpg`. Add nullable `photo_path_2` = `…/1.jpg`. Download script caches both under `.tmp/`; import `--upload-photos` uploads under `PHOTO_STORAGE_ROOT=exercise` → `exercise/free-exercise-db/…`. Detail page shows two images; grid keeps the first.

**Decisions:**
- No Gym visual / hasaneyldrm media (© — still out of scope).
- Do not rewrite 0013; migration `0014` ALTER + backfill via `replace(photo_path, '/0.jpg', '/1.jpg')`.
- Inner Storage prefix `exercise-photos/` unchanged (8576a2d).

## GWT

- Given a free_exercise_db row with `photo_path` ending `/0.jpg`, when 0014 runs, Then `photo_path_2` ends `/1.jpg`.
- Given both objects in Storage, when opening `/exercises/:slug`, Then both images load.
- Given download script, when run twice, Then existing files are skipped.

## Tasks

1. `scripts/download_free_exercise_db_photos.py`
2. Migration 0014 + import upload both + seed generator includes `photo_path_2`
3. Backend DTO/repo/tests; FE types + detail UI
4. Docs delta: cloud-setup / database-schema / ADR note
