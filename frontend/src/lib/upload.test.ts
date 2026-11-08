import { afterEach, describe, expect, it, vi } from 'vitest';
import { MAX_UPLOAD_BYTES, fitWithin, shrinkPhoto, tooLargeMessage } from './upload';

describe('fitWithin', () => {
	it('shrinks the longer side to the limit and keeps the aspect ratio', () => {
		expect(fitWithin(4000, 3000, 1600)).toEqual({ width: 1600, height: 1200 });
		expect(fitWithin(3000, 4000, 1600)).toEqual({ width: 1200, height: 1600 });
	});
	it('never enlarges a small photo', () => {
		expect(fitWithin(800, 600, 1600)).toEqual({ width: 800, height: 600 });
	});
	it('keeps very thin images at least one pixel wide', () => {
		expect(fitWithin(10000, 2, 1600)).toEqual({ width: 1600, height: 1 });
	});
	it('handles nonsense sizes without dividing by zero', () => {
		expect(fitWithin(0, 100, 1600)).toEqual({ width: 0, height: 0 });
		expect(fitWithin(NaN, 100, 1600)).toEqual({ width: 0, height: 0 });
	});
});

describe('tooLargeMessage', () => {
	it('is null when the upload fits', () => {
		expect(tooLargeMessage(MAX_UPLOAD_BYTES)).toBeNull();
		expect(tooLargeMessage(0)).toBeNull();
	});
	it('explains what to do when it does not', () => {
		const msg = tooLargeMessage(5_300_000);
		expect(msg).toContain('5.3 MB');
		expect(msg).toContain('shorter recording');
	});
});

describe('shrinkPhoto', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});
	it('returns the original file when the browser cannot decode images', async () => {
		const file = new File(['x'], 'leaf.heic', { type: 'image/heic' });
		vi.stubGlobal('createImageBitmap', undefined);
		expect(await shrinkPhoto(file)).toBe(file);
	});
	it('returns the original file when decoding fails', async () => {
		const file = new File(['not an image'], 'leaf.jpg', { type: 'image/jpeg' });
		vi.stubGlobal('createImageBitmap', () => Promise.reject(new Error('bad image')));
		expect(await shrinkPhoto(file)).toBe(file);
	});
});
