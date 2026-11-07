import { defineConfig, devices } from '@playwright/test';

// End-to-end tests run against `vite preview` of a production build, so build first:
//   VITE_API_URL=https://kisan-mitra-api.vercel.app npm run build && npm run test:e2e
// Every request to the backend is mocked in the tests; nothing leaves the machine.
const PORT = 4173;
const CI = !!process.env.CI;

export default defineConfig({
	testDir: 'e2e',
	timeout: 30_000,
	expect: { timeout: 5_000 },
	fullyParallel: false,
	workers: 1,
	forbidOnly: CI,
	retries: CI ? 1 : 0,
	reporter: CI ? [['list'], ['github']] : 'list',
	use: {
		baseURL: `http://localhost:${PORT}`,
		locale: 'gu-IN',
		timezoneId: 'Asia/Kolkata',
		trace: 'retain-on-failure'
	},
	projects: [
		{
			name: 'chromium',
			use: {
				...devices['Desktop Chrome'],
				// CI installs Playwright's Chromium; locally an installed Chrome is enough.
				...(CI ? {} : { launchOptions: { executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' } })
			}
		}
	],
	webServer: {
		command: `npm run preview -- --port ${PORT} --strictPort`,
		url: `http://localhost:${PORT}`,
		// Never reuse: a preview started before the last build serves stale files.
		reuseExistingServer: false,
		timeout: 60_000
	}
});
