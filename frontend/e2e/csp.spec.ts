import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { answer, GU_QUESTION, mockNetwork, openPage } from './fixtures';

// `vite preview` does not apply vercel.json, so the page is served here with the headers
// Vercel would send, read from vercel.json at test time. Together with the <meta> policy
// SvelteKit writes into the page, that is the policy a visitor's browser enforces.
const vercel = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url), 'utf8')) as {
	headers: { source: string; headers: { key: string; value: string }[] }[];
};
const HEADERS = Object.fromEntries(
	vercel.headers
		.find((h) => h.source === '/(.*)')!
		.headers.map((h) => [h.key.toLowerCase(), h.value])
);

type Violation = { directive: string; blocked: string };

/** Serves the built page with vercel.json's headers and records every CSP violation and console error. */
async function underVercelHeaders(page: Page) {
	const problems = { violations: [] as Violation[], console: [] as string[] };
	await page.exposeFunction('__cspViolation', (v: Violation) => problems.violations.push(v));
	await page.addInitScript(() => {
		document.addEventListener('securitypolicyviolation', (e) => {
			(window as any).__cspViolation({ directive: e.effectiveDirective, blocked: e.blockedURI });
		});
	});
	page.on('console', (msg) => {
		if (msg.type() === 'error') problems.console.push(msg.text());
	});
	page.on('pageerror', (err) => problems.console.push(String(err)));
	// Registered after mockNetwork, so it is asked first; anything but the page falls back.
	await page.route('**/*', async (route) => {
		if (route.request().resourceType() !== 'document') return route.fallback();
		const response = await route.fetch();
		await route.fulfill({ response, headers: { ...response.headers(), ...HEADERS } });
	});
	return problems;
}

test('connect-src has one source: the built page names the API origin, the header does not', () => {
	const html = readFileSync(new URL('../build/index.html', import.meta.url), 'utf8');
	const meta =
		html.match(/<meta http-equiv="content-security-policy" content="([^"]+)"/)?.[1] ?? '';
	const api = meta.match(/connect-src 'self' (\S+);/)?.[1];
	expect(api, 'the built page has a connect-src with the API origin').toMatch(/^https:\/\//);
	// Two copies of the origin could disagree (a preview built with another API would be
	// blocked by a header that names production), so only the build-time meta tag sets it.
	expect(HEADERS['content-security-policy']).not.toContain('connect-src');
	// Scripts are allowed by hash, never by 'unsafe-inline'.
	expect(meta).toMatch(/script-src 'self' 'sha256-[A-Za-z0-9+/=]+'/);
	expect(meta + HEADERS['content-security-policy']).not.toMatch(/script-src[^;]*unsafe-inline/);
});

test('the Gujarati journey runs under the production CSP with no violation', async ({ page }) => {
	const mock = await mockNetwork(page, answer('2026-11-07', '2026-11-08', '2026-11-09'));
	const problems = await underVercelHeaders(page);
	const response = page.waitForResponse((r) => r.request().resourceType() === 'document');
	await openPage(page);
	expect((await response).headers()['content-security-policy']).toBe(
		HEADERS['content-security-policy']
	);

	await page.getByRole('combobox', { name: 'Language' }).selectOption('gu');
	await page.getByRole('textbox', { name: 'Or type it' }).fill(GU_QUESTION);
	await page.getByRole('button', { name: 'Get advice' }).click();
	await expect(page.getByRole('heading', { name: 'Answer' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'સલાહ' })).toBeVisible();
	await expect(page.locator('.weather li')).toHaveCount(3);
	await page.evaluate(() => document.fonts.ready);

	expect(mock.analyzeBodies).toHaveLength(1);
	expect(problems.violations).toEqual([]);
	expect(problems.console).toEqual([]);
	expect(mock.blocked).toEqual([]);

	// And the policy is really enforced: an injected inline script does not run.
	const ran = await page.evaluate(() => {
		const s = document.createElement('script');
		s.textContent = 'window.__injected = true';
		document.head.append(s);
		return (window as any).__injected === true;
	});
	expect(ran).toBe(false);
	await expect.poll(() => problems.violations.map((v) => v.directive)).toContain('script-src-elem');
});
