/**
 * Read an answer aloud with the browser's speech synthesis, robustly:
 * - pick an installed voice for the language; with none, say so instead of staying silent
 *   (most desktops have no Gujarati voice, and an utterance with `lang` set but no
 *   matching voice is dropped or read in the wrong language);
 * - speak in sentence-sized chunks, because Chrome stops a long utterance after ~15 s;
 * - queue after `cancel()` on the next tick, because Chrome can drop an utterance queued
 *   in the same tick.
 */

export type Lang = 'gu' | 'hi' | 'en';
export const BCP47: Record<Lang, string> = { gu: 'gu-IN', hi: 'hi-IN', en: 'en-IN' };
const MAX_CHUNK = 180;

export interface VoiceLike {
	lang: string;
	name: string;
	localService?: boolean;
}

/** The best installed voice for a language: exact locale, then any of the language, else null. */
export function pickVoice<V extends VoiceLike>(voices: readonly V[], lang: Lang): V | null {
	const want = BCP47[lang].toLowerCase();
	const norm = (v: V) => v.lang.replace('_', '-').toLowerCase();
	const exact = voices.filter((v) => norm(v) === want);
	const family = voices.filter((v) => norm(v).split('-')[0] === lang);
	const pool = exact.length ? exact : family;
	// Prefer an on-device voice: it works offline and starts at once.
	return pool.find((v) => v.localService) ?? (pool.length > 0 ? pool[0] : null);
}

/** Plain text for speech: no markdown symbols, sentences of at most MAX_CHUNK characters. */
export function speechChunks(text: string): string[] {
	const plain = text
		.replace(/[*#|_>`]/g, '')
		.replace(/\s+/g, ' ')
		.trim();
	if (!plain) return [];
	const sentences = plain.match(/[^.!?।]+[.!?।]*\s*/g) ?? [plain];
	const chunks: string[] = [];
	for (const raw of sentences) {
		let s = raw.trim();
		while (s.length > MAX_CHUNK) {
			const cut = s.lastIndexOf(' ', MAX_CHUNK);
			const at = cut > 40 ? cut : MAX_CHUNK;
			chunks.push(s.slice(0, at).trim());
			s = s.slice(at).trim();
		}
		if (s) chunks.push(s);
	}
	return chunks;
}

export interface SynthLike {
	speaking: boolean;
	pending: boolean;
	cancel(): void;
	speak(u: SpeechSynthesisUtterance): void;
	getVoices(): SpeechSynthesisVoice[];
	addEventListener(type: 'voiceschanged', fn: () => void): void;
	removeEventListener(type: 'voiceschanged', fn: () => void): void;
}

/** Voices load asynchronously in Chrome: wait for them briefly. */
export function loadVoices(synth: SynthLike, timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
	const now = synth.getVoices();
	if (now.length) return Promise.resolve(now);
	return new Promise((resolve) => {
		const done = () => {
			synth.removeEventListener('voiceschanged', done);
			clearTimeout(timer);
			resolve(synth.getVoices());
		};
		const timer = setTimeout(done, timeoutMs);
		synth.addEventListener('voiceschanged', done);
	});
}

export type SpeakResult = 'speaking' | 'no-voice' | 'empty';

export interface SpeakOptions {
	synth: SynthLike;
	makeUtterance?: (text: string) => SpeechSynthesisUtterance;
	onEnd?: () => void;
	defer?: (fn: () => void) => void;
}

export async function speak(text: string, lang: Lang, opts: SpeakOptions): Promise<SpeakResult> {
	const { synth, onEnd } = opts;
	const make = opts.makeUtterance ?? ((t: string) => new SpeechSynthesisUtterance(t));
	const defer = opts.defer ?? ((fn: () => void) => setTimeout(fn, 0));
	const chunks = speechChunks(text);
	if (!chunks.length) return 'empty';
	const voice = pickVoice(await loadVoices(synth), lang);
	if (!voice) return 'no-voice';
	synth.cancel();
	defer(() => {
		chunks.forEach((chunk, i) => {
			const u = make(chunk);
			u.voice = voice;
			u.lang = voice.lang;
			if (i === chunks.length - 1 && onEnd) {
				u.onend = onEnd;
				u.onerror = onEnd;
			}
			synth.speak(u);
		});
	});
	return 'speaking';
}

export const NO_VOICE_MESSAGE: Record<Lang, string> = {
	gu: 'This device has no Gujarati voice installed, so the answer cannot be read aloud here. On Android, add Gujarati in Settings → Text-to-speech.',
	hi: 'This device has no Hindi voice installed, so the answer cannot be read aloud here. On Android, add Hindi in Settings → Text-to-speech.',
	en: 'This device has no English voice for reading aloud.'
};
