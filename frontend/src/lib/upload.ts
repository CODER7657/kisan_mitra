// Keeps every request under the host's body limit. Vercel functions accept about 4.5 MB per
// request, and a phone photo is often 3–8 MB, so photos are shrunk in the browser first.
// The classifier works at 224 px, so 1600 px loses nothing it uses.

export const MAX_UPLOAD_BYTES = 4_000_000; // headroom under 4.5 MB for the multipart wrapper
export const MAX_PHOTO_SIDE = 1600;
export const MAX_RECORDING_MS = 60_000;

/** The largest size with the same aspect ratio whose longer side is at most `max`. */
export function fitWithin(width: number, height: number, max: number): { width: number; height: number } {
	if (!(width > 0) || !(height > 0)) return { width: 0, height: 0 };
	const scale = Math.min(1, max / Math.max(width, height));
	return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

/** A message for the farmer when the upload is still too big, or null when it fits. */
export function tooLargeMessage(totalBytes: number, limit: number = MAX_UPLOAD_BYTES): string | null {
	if (totalBytes <= limit) return null;
	const mb = (totalBytes / 1_000_000).toFixed(1);
	return `The photo and recording together are ${mb} MB, over the ${(limit / 1_000_000).toFixed(0)} MB limit. Use a shorter recording or a smaller photo.`;
}

/**
 * The photo as a JPEG whose longer side is at most MAX_PHOTO_SIDE, or the original file when
 * it is already small enough, when shrinking wouldn't help, or when this browser can't decode
 * it (some HEIC files). Runs entirely on the device.
 */
export async function shrinkPhoto(file: File, maxSide = MAX_PHOTO_SIDE, quality = 0.85): Promise<Blob> {
	if (typeof createImageBitmap !== 'function') return file;
	let bitmap: ImageBitmap;
	try {
		bitmap = await createImageBitmap(file);
	} catch {
		return file;
	}
	const { width, height } = fitWithin(bitmap.width, bitmap.height, maxSide);
	if (width === bitmap.width && height === bitmap.height && file.size <= 1_500_000) {
		bitmap.close();
		return file;
	}
	const canvas = document.createElement('canvas');
	canvas.width = width;
	canvas.height = height;
	canvas.getContext('2d')?.drawImage(bitmap, 0, 0, width, height);
	bitmap.close();
	const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
	return blob && blob.size < file.size ? blob : file;
}
