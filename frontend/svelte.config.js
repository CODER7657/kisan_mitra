import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		// The site is one prerendered page that calls the backend from the browser, so it is
		// plain static files. On Vercel, adapter-static writes Vercel's output format itself.
		adapter: adapter(),
		// The page's CSS is a few kB: inline it so the first paint does not wait on a request.
		inlineStyleThreshold: 16384
	}
};

export default config;
