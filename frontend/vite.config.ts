import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import process from 'node:process';
import { loadEnv, type Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import { productionProblem } from './src/lib/api.ts';

// The backend the page calls. A production build reads VITE_API_URL (the build refuses to
// run without it, see requireApiUrl); `vite dev` may fall back to the local backend.
const PRODUCTION_API: HostOrigin = 'https://kisan-mitra-api.vercel.app';

/** What SvelteKit accepts as a CSP host source: scheme://name.tld[:port] or localhost. */
type HostOrigin = `${string}://${string}.${string}` | `${string}://localhost:${number}`;

function isHostOrigin(value: string): value is HostOrigin {
	return /^[a-z][a-z0-9+.-]*:\/\/([^/:]+\.[^/:]+|localhost:\d+)(:\d+)?$/i.test(value);
}

/** The origin (scheme://host[:port]) of a URL, or null when it is not one. */
function origin(url: string): HostOrigin | null {
	try {
		const value = new URL(url).origin;
		return isHostOrigin(value) ? value : null;
	} catch {
		return null;
	}
}

// A production build without a real backend URL would ship a page that calls localhost.
// Checked when bundling starts, so tools that only read this config still work.
function requireApiUrl(): Plugin {
	let problem: string | null = null;
	return {
		name: 'kisan-mitra:require-api-url',
		apply: 'build',
		configResolved(config) {
			const url: unknown = config.env.VITE_API_URL;
			problem =
				config.mode === 'production'
					? productionProblem(typeof url === 'string' ? url : undefined)
					: null;
		},
		buildStart() {
			if (problem) {
				this.error(
					`${problem}. Set it to the backend's https URL, e.g. https://kisan-mitra-api.vercel.app`
				);
			}
		}
	};
}

export default defineConfig(({ command, mode }) => {
	// Anything but `vite build` (vite dev, svelte-kit sync, checks, tests) is dev.
	const dev = command !== 'build';
	// Read VITE_API_URL the way Vite does: process env first, then .env, .env.production, ...
	const env = { ...loadEnv(mode, process.cwd(), 'VITE_'), ...process.env };
	const apiOrigins: HostOrigin[] = [origin(env.VITE_API_URL ?? '') ?? PRODUCTION_API];
	if (dev) apiOrigins.push('http://localhost:8000');

	return {
		plugins: [
			requireApiUrl(),
			sveltekit({
				preprocess: vitePreprocess(),
				// The site is one prerendered page that calls the backend from the browser, so it
				// is plain static files. On Vercel, adapter-static writes Vercel's output format.
				adapter: adapter(),
				// The page's CSS is a few kB: inline it so the first paint does not wait on a request.
				inlineStyleThreshold: 16384,
				// Content Security Policy as a <meta> tag in the prerendered page. `hash` mode adds
				// the sha256 of SvelteKit's inline start-up script to script-src, so no
				// 'unsafe-inline' for scripts. Styles need 'unsafe-inline': the CSS is inlined
				// (above) and Svelte sets style attributes. This tag is the only place connect-src
				// is set, from the URL the bundle was built with, so the two can never disagree.
				// frame-ancestors cannot be set from a <meta> tag; vercel.json sends it, with the
				// rest of the build-independent policy, as a header.
				csp: {
					mode: 'hash',
					directives: {
						'default-src': ['self'],
						'script-src': ['self'],
						'style-src': ['self', 'unsafe-inline'],
						'img-src': ['self', 'data:', 'blob:'],
						'media-src': ['self', 'blob:'],
						'font-src': ['self'],
						'connect-src': ['self', ...apiOrigins],
						'object-src': ['none'],
						'base-uri': ['self'],
						'form-action': ['self']
					}
				}
			})
		],
		test: { include: ['src/**/*.test.ts'] }
	};
});
