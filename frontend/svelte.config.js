import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import adapter from '@sveltejs/adapter-vercel'; // CORRECT: We are now explicitly using the Vercel adapter.

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		// This tells SvelteKit to build the output specifically for Vercel's infrastructure,
		// which includes correctly building our API serverless functions.
		adapter: adapter()
	}
};

export default config;
