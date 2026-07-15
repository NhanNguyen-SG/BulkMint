export const MAX_IMAGE_BYTES = 25 * 1024 * 1024;

export const IMAGE_ACCEPT =
  "image/jpeg,image/png,image/webp,image/heic,image/heif,image/avif,.jpg,.jpeg,.png,.webp,.heic,.heif,.avif";

const ALLOWED_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
  "image/avif",
]);
const ALLOWED_IMAGE_EXTENSIONS = new Set([
  "jpg",
  "jpeg",
  "png",
  "webp",
  "heic",
  "heif",
  "avif",
]);
const GENERIC_IMAGE_TYPES = new Set(["", "application/octet-stream"]);

export const BROWSER_PREVIEW_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/avif",
]);

export function validateImageFile(file: File): string | null {
  const contentType = file.type.trim().toLowerCase();
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const hasAcceptedType = ALLOWED_IMAGE_TYPES.has(contentType);
  const hasAcceptedFallbackExtension =
    GENERIC_IMAGE_TYPES.has(contentType) &&
    ALLOWED_IMAGE_EXTENSIONS.has(extension);

  if (!hasAcceptedType && !hasAcceptedFallbackExtension) {
    return "Choose a JPEG, PNG, WebP, HEIC, HEIF, or AVIF image.";
  }

  if (file.size > MAX_IMAGE_BYTES) {
    return "Image must be 25 MB or smaller.";
  }

  return null;
}
