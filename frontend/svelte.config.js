import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import process from 'node:process';
import { loadEnv } from 'vite';

// The backend the page calls. A production build reads VITE_API_URL (the build refuses to
// run without it, see vite.config.ts); `vite dev` may fall back to the local backend.
const PRODUCTION_API = 'https://kisan-mitra-api.vercel.app';
// Anything but `vite build` (plain `vite`, `vite dev`, svelte-kit sync, checks) is dev.
const BUILD = process.argv.includes('build');
const DEV = !BUILD;
// Read VITE_API_URL the way Vite does: process env first, then .env, .env.production, ...
const env = {
	...loadEnv(BUILD ? 'production' : 'development', process.cwd(), 'VITE_'),
	...process.env
};

/** The origin (scheme://host[:port]) of a URL, or null when it is not one. */
function origin(url) {
	try {
		return new URL(url).origin;
	} catch {
		return null;
	}
}

const apiOrigins = [origin(env.VITE_API_URL ?? '') ?? PRODUCTION_API];
if (DEV) apiOrigins.push('http://localhost:8000');

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		// The site is one prerendered page that calls the backend from the browser, so it is
		// plain static files. On Vercel, adapter-static writes Vercel's output format itself.
		adapter: adapter(),
		// The page's CSS is a few kB: inline it so the first paint does not wait on a request.
		inlineStyleThreshold: 16384,
		// Content Security Policy as a <meta> tag in the prerendered page. `hash` mode adds the
		// sha256 of SvelteKit's inline start-up script to script-src, so no 'unsafe-inline' for
		// scripts. Styles need 'unsafe-inline': the CSS is inlined (above) and Svelte sets
		// style attributes. This tag is the only place connect-src is set, from the URL the
		// bundle was built with, so the two can never disagree. frame-ancestors cannot be set
		// from a <meta> tag; vercel.json sends it, with the rest of the build-independent
		// policy, as a header.
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
	}
};

export default config;
