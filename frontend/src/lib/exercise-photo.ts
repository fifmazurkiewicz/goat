const BUCKET = "exercise-photos";

/**
 * `photo_path` from the API is either a full URL or a path inside the bucket
 * (`free-exercise-db/<Id>/0.jpg` — seed 0013).
 */
export function exercisePhotoSrc(photoPath: string | null | undefined): string | null {
  if (!photoPath) return null;
  if (/^https?:\/\//i.test(photoPath)) return photoPath;
  const base = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, "");
  if (!base) return photoPath;
  return `${base}/storage/v1/object/public/${BUCKET}/${photoPath.replace(/^\/+/, "")}`;
}
