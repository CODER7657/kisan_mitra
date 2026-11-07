import { expect, test, type Page } from '@playwright/test';
import {
	answer,
	expectNoHorizontalScroll,
	expectReadableText,
	expectTouchTargets,
	GU_QUESTION,
	mockNetwork,
	openPage,
	seriousA11yViolations
} from './fixtures';

const SIZES = [
	{ name: 'phone 375x812', width: 375, height: 812 },
	{ name: 'tablet 768x1024', width: 768, height: 1024 },
	{ name: 'desktop 1280x800', width: 1280, height: 800 }
];

// Midday and night on 7 Nov 2026 in India (the config's time zone).
const NOON = new Date('2026-11-07T12:00:00+05:30');
const NIGHT = new Date('2026-11-07T21:30:00+05:30');
const reply = answer('2026-11-07', '2026-11-08', '2026-11-09');

async function askInGujarati(page: Page) {
	await page.getByRole('combobox', { name: 'Language' }).selectOption('gu');
	await page.getByRole('textbox', { name: 'Or type it' }).fill(GU_QUESTION);
	await page.getByRole('button', { name: 'Get advice' }).click();
	await expect(page.getByRole('heading', { name: 'Answer' })).toBeVisible();
}

for (const size of SIZES) {
	test.describe(size.name, () => {
		test.use({ viewport: { width: size.width, height: size.height } });

		test('initial page is accessible, readable and fits the screen', async ({ page }) => {
			const mock = await mockNetwork(page, reply);
			await openPage(page);
			await expect(page.getByRole('heading', { level: 1, name: 'Ask about your crop.' })).toBeVisible();
			await page.evaluate(() => document.fonts.ready);
			expect(await seriousA11yViolations(page)).toEqual([]);
			await expectNoHorizontalScroll(page);
			await expectTouchTargets(page);
			await expectReadableText(page);
			expect(mock.blocked).toEqual([]);
		});

		test('Gujarati question gets a Gujarati answer with a forecast strip', async ({ page }) => {
			await page.clock.setFixedTime(NOON);
			const mock = await mockNetwork(page, reply);
			await openPage(page);
			await askInGujarati(page);

			// The question and the chosen language reached the (mocked) backend.
			expect(mock.analyzeBodies).toHaveLength(1);
			expect(mock.analyzeBodies[0]).toContain(GU_QUESTION);
			expect(mock.analyzeBodies[0]).toMatch(/name="language"\r\n\r\ngu\r\n/);

			await expect(page.getByRole('heading', { name: 'સલાહ' })).toBeVisible();
			await expect(page.getByText('ખેતરમાંથી વધારાનું પાણી કાઢો.')).toBeVisible();

			// One forecast entry per day, each led by the matching line icon.
			const days = page.locator('.weather li');
			await expect(days).toHaveCount(3);
			await expect(days.nth(0)).toHaveAttribute('data-sky', 'clear-day');
			await expect(days.nth(0).locator('svg.lucide-sun')).toBeVisible();
			await expect(days.nth(0)).toContainText('Clear');
			await expect(days.nth(1)).toHaveAttribute('data-sky', 'rain');
			await expect(days.nth(1).locator('svg.lucide-cloud-rain')).toBeVisible();
			await expect(days.nth(1)).toContainText('12.4 mm');
			await expect(days.nth(2)).toHaveAttribute('data-sky', 'showers');
			await expect(days.nth(2).locator('svg.lucide-cloud-drizzle')).toBeVisible();

			await page.evaluate(() => document.fonts.ready);
			expect(await seriousA11yViolations(page)).toEqual([]);
			await expectNoHorizontalScroll(page);
			await expectTouchTargets(page);
			await expectReadableText(page);
			expect(mock.blocked).toEqual([]);
		});
	});
}

test.describe('weather strip at night', () => {
	test.use({ viewport: { width: 375, height: 812 } });

	test("today's clear sky shows the moon after dark", async ({ page }) => {
		await page.clock.setFixedTime(NIGHT);
		await mockNetwork(page, reply);
		await openPage(page);
		await askInGujarati(page);
		const today = page.locator('.weather li').first();
		await expect(today).toHaveAttribute('data-sky', 'clear-night');
		await expect(today.locator('svg.lucide-moon')).toBeVisible();
		// Tomorrow is still a daytime forecast.
		await expect(page.locator('.weather li').nth(1).locator('svg.lucide-cloud-rain')).toBeVisible();
	});
});

test('a backend error is shown in the form, still readable and accessible', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await page.route('**/*', (route) => {
		const url = new URL(route.request().url());
		if (url.hostname === 'localhost') return route.continue();
		if (url.pathname.endsWith('/analyze/')) return route.fulfill({ status: 503, body: '<html>busy</html>' });
		return route.fulfill({ json: { status: 'ok' } });
	});
	await openPage(page);
	await page.getByRole('textbox', { name: 'Or type it' }).fill(GU_QUESTION);
	await page.getByRole('button', { name: 'Get advice' }).click();
	await expect(page.getByRole('alert')).toContainText('starting up or busy');
	expect(await seriousA11yViolations(page)).toEqual([]);
	await expectReadableText(page);
});

test('no emoji are used as icons', async ({ page }) => {
	await mockNetwork(page, reply);
	await openPage(page);
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/\p{Extended_Pictographic}/u);
});

test('a forecast day with no numbers shows a dash and a plain cloud, never "null"', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	const gap = answer('2026-11-07', '2026-11-08', '2026-11-09');
	gap.weather.days[1] = { date: '2026-11-08', rain_mm: null, rain_chance_pct: null } as never;
	await mockNetwork(page, gap);
	await openPage(page);
	await askInGujarati(page);
	const day = page.locator('.weather li').nth(1);
	await expect(day).toHaveAttribute('data-sky', 'unknown');
	await expect(day.locator('.mm')).toHaveText('–');
	await expect(day.locator('.pct')).toHaveText('–');
	await expect(page.locator('.weather')).not.toContainText('null');
});
