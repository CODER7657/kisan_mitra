// Where the backend lives. Production builds must name it in VITE_API_URL; only the
// dev server may fall back to a local backend.

export const DEV_API_URL = 'http://localhost:8000';

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '0.0.0.0']);

/** Why `url` can't be a production backend, or null if it can. */
export function productionProblem(url: string | undefined): string | null {
	const value = (url ?? '').trim();
	if (!value) return 'VITE_API_URL is not set';
	let parsed: URL;
	try {
		parsed = new URL(value);
	} catch {
		return `VITE_API_URL is not a URL: ${value}`;
	}
	if (parsed.protocol !== 'https:') return `VITE_API_URL must use https: ${value}`;
	if (LOCAL_HOSTS.has(parsed.hostname)) return `VITE_API_URL points at this machine: ${value}`;
	return null;
}

/**
 * The JSON body of a backend reply, or an Error with a message a farmer can act on. A
 * proxy in front of a sleeping or crashed backend answers with HTML, not JSON.
 */
export async function readReply(response: Response): Promise<any> {
	let data: any = null;
	try {
		data = await response.json();
	} catch {
		// not JSON
	}
	if (response.ok && data) return data;
	if (data && typeof data.detail === 'string') throw new Error(data.detail);
	if (response.status === 413) {
		throw new Error(
			'The photo or recording is too large to send. Use a smaller photo or a shorter recording.'
		);
	}
	if ([502, 503, 504].includes(response.status)) {
		throw new Error('The service is starting up or busy. Please try again in a minute.');
	}
	throw new Error(`Something went wrong (HTTP ${response.status}). Please try again.`);
}

/** The backend base URL without a trailing slash, or null when the service is unavailable. */
export function resolveApiUrl(url: string | undefined, dev: boolean): string | null {
	const value = (url ?? '').trim();
	if (dev) return (value || DEV_API_URL).replace(/\/+$/, '');
	return productionProblem(value) ? null : value.replace(/\/+$/, '');
}
