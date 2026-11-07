import { describe, expect, it } from 'vitest';
import { formatDuration, loadingMessage } from './ui';

describe('formatDuration', () => {
	it('formats minutes and padded seconds', () => {
		expect(formatDuration(0)).toBe('0:00');
		expect(formatDuration(9_999)).toBe('0:09');
		expect(formatDuration(65_000)).toBe('1:05');
		expect(formatDuration(60_000)).toBe('1:00');
	});

	it('treats bad input as zero', () => {
		expect(formatDuration(-5)).toBe('0:00');
		expect(formatDuration(Number.NaN)).toBe('0:00');
		expect(formatDuration(Number.POSITIVE_INFINITY)).toBe('0:00');
	});
});

describe('loadingMessage', () => {
	it('moves from preparing, to still working, to taking long', () => {
		expect(loadingMessage(0)).toBe('Preparing your answer.');
		expect(loadingMessage(7_999)).toBe('Preparing your answer.');
		expect(loadingMessage(8_000)).toMatch(/^Still working/);
		expect(loadingMessage(24_999)).toMatch(/^Still working/);
		expect(loadingMessage(25_000)).toMatch(/longer than usual/);
	});

	it('never promises a duration', () => {
		for (const t of [0, 10_000, 60_000]) expect(loadingMessage(t)).not.toMatch(/minute|second/);
	});

	it('handles bad input', () => {
		expect(loadingMessage(Number.NaN)).toBe('Preparing your answer.');
		expect(loadingMessage(-1)).toBe('Preparing your answer.');
	});
});
