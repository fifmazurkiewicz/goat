-- Dual photos for free-exercise-db: start (0.jpg) + finish (1.jpg).
-- photo_path stays the first frame; photo_path_2 is the second.
-- Backfill from existing relative paths — no need to rewrite seed 0013.

alter table public.exercises
  add column if not exists photo_path_2 text;

update public.exercises
set photo_path_2 = replace(photo_path, '/0.jpg', '/1.jpg')
where source = 'free_exercise_db'
  and photo_path is not null
  and photo_path like '%/0.jpg'
  and (photo_path_2 is null or photo_path_2 = '');
