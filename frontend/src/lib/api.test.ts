import { describe, expect, it } from 'vitest';
import { DEV_API_URL, productionProblem, readReply, resolveApiUrl } from './api';

describe('productionProblem', () => {
	it('accepts a public https URL', () => {
		expect(productionProblem('https://kisan-mitra-api.onrender.com')).toBeNull();
	});

	it.each([undefined, '', '   '])('rejects a missing URL (%j)', (url) => {
		expect(productionProblem(url)).toMatch(/not set/);
	});

	it.each([
		'http://localhost:8000',
		'https://localhost:8000',
		'https://127.0.0.1',
		'https://[::1]:8000',
		'https://0.0.0.0'
	])('rejects a local backend (%s)', (url) => {
		expect(productionProblem(url)).not.toBeNull();
	});

	it('rejects plain http, which a https page cannot call', () => {
		expect(productionProblem('http://kisan-mitra-api.onrender.com')).toMatch(/https/);
	});

	it.each(['onrender.com', 'not a url', 'ftp://example.com'])(
		'rejects a malformed URL (%s)',
		(url) => {
			expect(productionProblem(url)).not.toBeNull();
		}
	);
});

describe('resolveApiUrl', () => {
	it('falls back to the local backend only in dev', () => {
		expect(resolveApiUrl(undefined, true)).toBe(DEV_API_URL);
		expect(resolveApiUrl(undefined, false)).toBeNull();
	});

	it('never lets a production build call localhost', () => {
		expect(resolveApiUrl('http://localhost:8000', false)).toBeNull();
	});

	it('trims trailing slashes and whitespace', () => {
		expect(resolveApiUrl(' https://api.example.org// ', false)).toBe('https://api.example.org');
		expect(resolveApiUrl('http://localhost:9000/', true)).toBe('http://localhost:9000');
	});
});

const reply = (status: number, body: string, type = 'application/json') =>
	new Response(body, { status, headers: { 'content-type': type } });

describe('readReply', () => {
	it('returns the JSON body of a good reply', async () => {
		await expect(readReply(reply(200, '{"analysis":"ok"}'))).resolves.toEqual({ analysis: 'ok' });
	});

	it("passes the backend's own error message through", async () => {
		await expect(
			readReply(reply(400, '{"detail":"Send a voice recording or type a question."}'))
		).rejects.toThrow('Send a voice recording or type a question.');
	});

	it('explains an HTML 502 from a sleeping backend instead of a JSON parse error', async () => {
		await expect(readReply(reply(502, '<html>Bad Gateway</html>', 'text/html'))).rejects.toThrow(
			/starting up/
		);
	});

	it("explains the host's HTML 413 for an upload that is too large", async () => {
		await expect(
			readReply(new Response('<html>Request Entity Too Large</html>', { status: 413 }))
		).rejects.toThrow('too large to send');
	});
	it('gives a plain message for other non-JSON failures', async () => {
		await expect(readReply(reply(500, 'oops', 'text/plain'))).rejects.toThrow('HTTP 500');
	});

	it('does not treat a non-string detail as a message', async () => {
		await expect(readReply(reply(422, '{"detail":[{"msg":"bad"}]}'))).rejects.toThrow('HTTP 422');
	});

	it('rejects a 200 that is not JSON', async () => {
		await expect(readReply(reply(200, '<html></html>', 'text/html'))).rejects.toThrow('HTTP 200');
	});
});
