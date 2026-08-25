const BUCKET = "exercise-photos";
/** Inner folder: bucket/exercise/free-exercise-db/<Id>/… */
const PHOTO_STORAGE_ROOT = "exercise";

function bucketObjectPath(photoPath: string): string {
  let path = photoPath.replace(/^\/+/, "");
  // Legacy manual upload used an inner folder also named `exercise-photos/`.
  if (path.startsWith("exercise-photos/")) {
    path = path.slice("exercise-photos/".length);
  }
  if (path.startsWith(`${PHOTO_STORAGE_ROOT}/`)) return path;
  return `${PHOTO_STORAGE_ROOT}/${path}`;
}

/**
 * `photo_path` from the API is either a full URL or a path inside the bucket
 * (`free-exercise-db/<Id>/0.jpg` — seed 0013; resolved under PHOTO_STORAGE_ROOT).
 */
export function exercisePhotoSrc(photoPath: string | null | undefined): string | null {
  if (!photoPath) return null;
  if (/^https?:\/\//i.test(photoPath)) return photoPath;
  const base = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, "");
  const objectPath = bucketObjectPath(photoPath);
  if (!base) return objectPath;
  return `${base}/storage/v1/object/public/${BUCKET}/${objectPath}`;
}
