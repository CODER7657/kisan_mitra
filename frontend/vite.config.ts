import { sveltekit } from '@sveltejs/kit/vite';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import { productionProblem } from './src/lib/api';

// A production build without a real backend URL would ship a page that calls localhost.
// Checked when bundling starts, so tools that only read this config still work.
function requireApiUrl(): Plugin {
	let problem: string | null = null;
	return {
		name: 'kisan-mitra:require-api-url',
		apply: 'build',
		configResolved(config) {
			problem = config.mode === 'production' ? productionProblem(config.env.VITE_API_URL) : null;
		},
		buildStart() {
			if (problem) {
				this.error(`${problem}. Set it to the backend's https URL, e.g. https://kisan-mitra-api.vercel.app`);
			}
		}
	};
}

export default defineConfig({
	plugins: [requireApiUrl(), sveltekit()],
	test: { include: ['src/**/*.test.ts'] }
});
