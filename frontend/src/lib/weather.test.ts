import { describe, expect, it } from 'vitest';
import { isNight, localDate, SKY_LABEL, skyFor, skyForDay, type Sky } from './weather';

const day = (rain_mm: number | null, rain_chance_pct: number | null, date = '2026-11-07') => ({
	date,
	rain_mm,
	rain_chance_pct
});

describe('skyFor', () => {
	it('reads heavy rain from the daily total', () => {
		expect(skyFor(day(15, 90))).toBe('heavy-rain');
		expect(skyFor(day(42.5, null))).toBe('heavy-rain');
	});

	it('reads rain from the total or a high chance', () => {
		expect(skyFor(day(1, 10))).toBe('rain');
		expect(skyFor(day(14.9, 50))).toBe('rain');
		expect(skyFor(day(0, 60))).toBe('rain');
		expect(skyFor(day(null, 85))).toBe('rain');
	});

	it('reads a chance of showers from a trace of rain or a middling chance', () => {
		expect(skyFor(day(0.4, 10))).toBe('showers');
		expect(skyFor(day(0, 30))).toBe('showers');
		expect(skyFor(day(0, 59))).toBe('showers');
	});

	it('shows a clear day by day and a clear night by night', () => {
		expect(skyFor(day(0, 5))).toBe('clear-day');
		expect(skyFor(day(0, 29), false)).toBe('clear-day');
		expect(skyFor(day(0, 0), true)).toBe('clear-night');
	});

	it('night never hides rain', () => {
		expect(skyFor(day(20, 100), true)).toBe('heavy-rain');
		expect(skyFor(day(0, 70), true)).toBe('rain');
	});

	it('falls back to unknown, never to sun, when it has nothing to go on', () => {
		expect(skyFor(day(null, null))).toBe('unknown');
		expect(skyFor(day(Number.NaN, Number.POSITIVE_INFINITY))).toBe('unknown');
		expect(skyFor(day(-1, -5))).toBe('unknown');
		expect(skyFor({})).toBe('unknown');
		expect(skyFor(null)).toBe('unknown');
		expect(skyFor(undefined, true)).toBe('unknown');
		expect(skyFor({ rain_mm: '5' as unknown as number, rain_chance_pct: null })).toBe('unknown');
	});

	it('uses whichever number is usable when the other is missing or bad', () => {
		expect(skyFor(day(Number.NaN, 0))).toBe('clear-day');
		expect(skyFor(day(3, null))).toBe('rain');
		expect(skyFor(day(-2, 40))).toBe('showers');
	});

	it('caps a chance above 100% instead of failing', () => {
		expect(skyFor(day(0, 250))).toBe('rain');
	});
});

describe('SKY_LABEL', () => {
	it('has a label for every sky', () => {
		const skies: Sky[] = ['heavy-rain', 'rain', 'showers', 'clear-day', 'clear-night', 'unknown'];
		for (const s of skies) expect(SKY_LABEL[s]).toMatch(/\S/);
	});
});

describe('localDate and isNight', () => {
	it('formats the local date like the forecast', () => {
		expect(localDate(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05');
		expect(localDate(new Date(2026, 10, 7, 0, 0))).toBe('2026-11-07');
	});

	it('treats 19:00 to 05:59 as night', () => {
		expect(isNight(new Date(2026, 10, 7, 5, 59))).toBe(true);
		expect(isNight(new Date(2026, 10, 7, 6, 0))).toBe(false);
		expect(isNight(new Date(2026, 10, 7, 18, 59))).toBe(false);
		expect(isNight(new Date(2026, 10, 7, 19, 0))).toBe(true);
	});
});

describe('skyForDay', () => {
	const tonight = new Date(2026, 10, 7, 21, 0);
	const noon = new Date(2026, 10, 7, 12, 0);

	it("shows the moon only on today's clear entry at night", () => {
		expect(skyForDay(day(0, 0, '2026-11-07'), tonight)).toBe('clear-night');
		expect(skyForDay(day(0, 0, '2026-11-08'), tonight)).toBe('clear-day');
		expect(skyForDay(day(0, 0, '2026-11-07'), noon)).toBe('clear-day');
	});

	it('handles a missing day', () => {
		expect(skyForDay(undefined, tonight)).toBe('unknown');
	});
});
