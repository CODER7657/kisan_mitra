import { expect, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export const GU_QUESTION = 'કપાસના પાન પીળા પડી ગયા છે';

/** A Gujarati answer with a three-day forecast: clear, rain, then a chance of showers. */
export function answer(today: string, tomorrow: string, dayAfter: string) {
	return {
		analysis:
			'## સલાહ\n\nકપાસના પાન પીળા પડવાનું કારણ નાઇટ્રોજનની ઉણપ અથવા પાણી ભરાવું હોઈ શકે.\n\n' +
			'- ખેતરમાંથી વધારાનું પાણી કાઢો.\n- કોઈ પણ દવા માટે તમારા KVK ની સલાહ લો.',
		transcript: '',
		question: GU_QUESTION,
		language: 'gu',
		photo: null,
		weather: {
			source: 'Open-Meteo forecast',
			days: [
				{ date: today, rain_mm: 0, rain_chance_pct: 5 },
				{ date: tomorrow, rain_mm: 12.4, rain_chance_pct: 85 },
				{ date: dayAfter, rain_mm: 0.4, rain_chance_pct: 40 }
			]
		},
		guard: { lines_removed: 0, kvk_added: true }
	};
}

export type Mock = { analyzeBodies: string[]; blocked: string[] };

/**
 * Serves the page from the local preview and mocks the backend: /health and /analyze/.
 * Anything else that would leave the machine is aborted and recorded, so a test can
 * assert that no real network was used.
 */
export async function mockNetwork(page: Page, reply: object): Promise<Mock> {
	const mock: Mock = { analyzeBodies: [], blocked: [] };
	await page.route('**/*', async (route: Route) => {
		const url = new URL(route.request().url());
		if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') return route.continue();
		if (url.pathname.endsWith('/health')) return route.fulfill({ json: { status: 'ok' } });
		if (url.pathname.endsWith('/analyze/') && route.request().method() === 'POST') {
			mock.analyzeBodies.push(route.request().postDataBuffer()?.toString('utf8') ?? '');
			return route.fulfill({ json: reply });
		}
		mock.blocked.push(url.href);
		return route.abort();
	});
	return mock;
}

/**
 * Opens the page and waits until it is interactive. The page is prerendered, so it is
 * visible before Svelte hydrates; it pings /health from onMount, which marks hydration.
 */
export async function openPage(page: Page) {
	await Promise.all([page.waitForRequest((r) => r.url().endsWith('/health')), page.goto('/')]);
}

/** WCAG 2.1 A and AA violations that are serious or critical. */
export async function seriousA11yViolations(page: Page) {
	const results = await new AxeBuilder({ page })
		.withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
		.analyze();
	return results.violations
		.filter((v) => v.impact === 'serious' || v.impact === 'critical')
		.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

/** The page never scrolls sideways. */
export async function expectNoHorizontalScroll(page: Page) {
	const { scroll, client } = await page.evaluate(() => ({
		scroll: document.documentElement.scrollWidth,
		client: document.documentElement.clientWidth
	}));
	expect(scroll, 'page is wider than the viewport').toBeLessThanOrEqual(client);
}

/** Every visible control is at least 48px tall (a checkbox counts its whole label). */
export async function expectTouchTargets(page: Page) {
	const small = await page.evaluate(() => {
		const selector = 'button, select, textarea, a[href], label.btn, input:not([type=hidden])';
		return Array.from(document.querySelectorAll<HTMLElement>(selector))
			.map((el) => {
				const target =
					el instanceof HTMLInputElement && el.type === 'checkbox'
						? (el.closest('label') ?? el)
						: el;
				const box = target.getBoundingClientRect();
				const hidden =
					box.width <= 1 || box.height <= 1 || getComputedStyle(target).visibility === 'hidden';
				return { what: target.outerHTML.slice(0, 80), height: box.height, hidden };
			})
			.filter((c) => !c.hidden && c.height < 48);
	});
	expect(small, 'controls shorter than 48px').toEqual([]);
}

/** Body text, and every piece of visible text on the page, is at least 18px. */
export async function expectReadableText(page: Page) {
	const { body, small } = await page.evaluate(() => {
		const tiny: { text: string; size: number }[] = [];
		const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
		for (let n = walker.nextNode(); n; n = walker.nextNode()) {
			const text = n.textContent?.trim();
			const el = n.parentElement;
			if (!text || !el || el.closest('script, style, option')) continue;
			const size = parseFloat(getComputedStyle(el).fontSize);
			if (size < 18) tiny.push({ text: text.slice(0, 40), size });
		}
		return { body: parseFloat(getComputedStyle(document.body).fontSize), small: tiny };
	});
	expect(body).toBeGreaterThanOrEqual(18);
	expect(small, 'text smaller than 18px').toEqual([]);
}
