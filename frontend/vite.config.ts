import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	// This is the crucial fix.
	// It tells Vite's server-side renderer (SSR) to NOT treat 'openai' as an external package.
	// This forces Vite/Rollup to correctly bundle it into your serverless function.
	ssr: {
		noExternal: ['openai']
	}
});
