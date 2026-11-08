// Small display helpers for the page, kept here so they can be tested without a browser.

/** 65_000 -> "1:05". Negative or non-finite input reads as 0:00. */
export function formatDuration(ms: number): string {
	const total = Number.isFinite(ms) && ms > 0 ? Math.floor(ms / 1000) : 0;
	const m = Math.floor(total / 60);
	const s = total % 60;
	return `${m}:${String(s).padStart(2, '0')}`;
}

/**
 * What the farmer sees while the answer is being prepared. It only says what is true at
 * that moment: no promised duration, and a plain note if it is taking unusually long.
 */
export function loadingMessage(elapsedMs: number): string {
	if (!(elapsedMs >= 8_000)) return 'Preparing your answer.';
	if (elapsedMs < 25_000)
		return 'Still working. Checking the photo, the weather and the safety rules.';
	return 'This is taking longer than usual. You can keep waiting, or go back and try again.';
}
