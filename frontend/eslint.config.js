// ESLint (flat config): typescript-eslint's strict, type-checked rules on the TypeScript and on
// the <script lang="ts"> of each .svelte file, plus eslint-plugin-svelte's recommended rules.
// Formatting is Prettier's job (`npm run format:check`); eslint-config-prettier turns off the
// rules that would disagree with it. Versions are pinned in package.json.
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';
import { defineConfig } from 'eslint/config';
import svelteConfig from './svelte.config.js';

export default defineConfig(
	{
		// .gitignore'd output, plus the generated SvelteKit types.
		ignores: [
			'build/',
			'.svelte-kit/',
			'.lighthouseci/',
			'test-results/',
			'playwright-report/',
			'node_modules/'
		]
	},
	js.configs.recommended,
	ts.configs.strictTypeChecked,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,
	{
		languageOptions: {
			globals: { ...globals.browser },
			parserOptions: {
				// The app (src/, vite.config.ts) and the Playwright specs have separate projects.
				project: ['./tsconfig.json', './e2e/tsconfig.json'],
				tsconfigRootDir: import.meta.dirname,
				extraFileExtensions: ['.svelte']
			}
		}
	},
	{
		rules: {
			// Numbers in messages ("HTTP 503", "4.2 MB") read fine; other non-strings stay errors.
			'@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }]
		}
	},
	{
		// Build config and the Playwright specs run in Node, not the browser.
		files: ['*.config.{js,ts}', 'e2e/**'],
		languageOptions: { globals: { ...globals.node } }
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: {
			parserOptions: {
				parser: ts.parser,
				svelteConfig
			}
		}
	},
	{
		// Plain-JS config files are in no TypeScript project: lint them without type information.
		files: ['**/*.js'],
		extends: [ts.configs.disableTypeChecked]
	}
);
