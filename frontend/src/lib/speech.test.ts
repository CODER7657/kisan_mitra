import { describe, expect, it, vi } from 'vitest';
import { pickVoice, speak, speechChunks, type SynthLike } from './speech';

const v = (lang: string, name = lang, localService = false) =>
	({ lang, name, localService }) as unknown as SpeechSynthesisVoice;

function fakeSynth(voices: SpeechSynthesisVoice[], late = false) {
	const spoken: SpeechSynthesisUtterance[] = [];
	const cancel = vi.fn();
	let listener: (() => void) | null = null;
	let ready = !late;
	const synth: SynthLike = {
		speaking: false,
		pending: false,
		cancel,
		speak: (u) => {
			spoken.push(u);
		},
		getVoices: () => (ready ? voices : []),
		addEventListener: (_t, fn) => {
			listener = fn;
		},
		removeEventListener: () => {
			listener = null;
		}
	};
	const loadNow = () => {
		ready = true;
		listener?.();
	};
	return { synth, spoken, loadNow, cancel };
}

const make = (t: string) => ({ text: t }) as SpeechSynthesisUtterance;
const now = (fn: () => void) => {
	fn();
};

describe('pickVoice', () => {
	it('prefers the exact locale, then the language, then an on-device voice', () => {
		const voices = [v('en-US'), v('gu-IN', 'remote'), v('gu-IN', 'local', true), v('hi-IN')];
		expect(pickVoice(voices, 'gu')?.name).toBe('local');
		expect(pickVoice([v('hi_IN', 'android-style')], 'hi')?.name).toBe('android-style');
		expect(pickVoice([v('en-GB')], 'en')?.lang).toBe('en-GB');
	});

	it('returns null when the device has no voice for the language', () => {
		expect(pickVoice([v('en-US'), v('hi-IN')], 'gu')).toBeNull();
		expect(pickVoice([], 'en')).toBeNull();
	});
});

describe('speechChunks', () => {
	it('strips markdown and splits on sentence ends, including the Devanagari danda', () => {
		expect(speechChunks('**Water** the field. Then wait!')).toEqual([
			'Water the field.',
			'Then wait!'
		]);
		expect(speechChunks('पानी दें। फिर रुकें।')).toEqual(['पानी दें।', 'फिर रुकें।']);
	});

	it('never yields a chunk Chrome would cut off', () => {
		const long = 'word '.repeat(200);
		const chunks = speechChunks(long);
		expect(chunks.length).toBeGreaterThan(1);
		expect(Math.max(...chunks.map((c) => c.length))).toBeLessThanOrEqual(180);
		expect(chunks.join(' ').replace(/\s+/g, ' ')).toBe(long.trim());
	});

	it('is empty for nothing to say', () => {
		expect(speechChunks('  ** # ')).toEqual([]);
	});
});

describe('speak', () => {
	it('speaks every chunk with the chosen voice, after cancelling what was playing', async () => {
		const { synth, spoken, cancel } = fakeSynth([v('en-US'), v('gu-IN', 'g', true)]);
		const onEnd = vi.fn();
		expect(await speak('એક. બે.', 'gu', { synth, makeUtterance: make, defer: now, onEnd })).toBe(
			'speaking'
		);
		expect(cancel).toHaveBeenCalledOnce();
		expect(spoken.map((u) => u.text)).toEqual(['એક.', 'બે.']);
		expect(spoken.every((u) => u.voice?.name === 'g' && u.lang === 'gu-IN')).toBe(true);
		expect(spoken[1]?.onend).toBe(onEnd);
	});

	it('reports a missing voice instead of failing silently', async () => {
		const { synth, spoken } = fakeSynth([v('en-US')]);
		expect(await speak('એક.', 'gu', { synth, makeUtterance: make, defer: now })).toBe('no-voice');
		expect(spoken).toEqual([]);
	});

	it('waits for voices that load late (Chrome)', async () => {
		const { synth, spoken, loadNow } = fakeSynth([v('hi-IN')], true);
		const pending = speak('नमस्ते।', 'hi', { synth, makeUtterance: make, defer: now });
		loadNow();
		expect(await pending).toBe('speaking');
		expect(spoken).toHaveLength(1);
	});

	it('queues on a later tick than cancel()', async () => {
		const { synth, spoken } = fakeSynth([v('en-IN')]);
		const later: (() => void)[] = [];
		await speak('Hello.', 'en', {
			synth,
			makeUtterance: make,
			defer: (fn) => {
				later.push(fn);
			}
		});
		expect(spoken).toEqual([]);
		later.forEach((fn) => {
			fn();
		});
		expect(spoken).toHaveLength(1);
	});

	it('says nothing for an empty answer', async () => {
		const { synth } = fakeSynth([v('en-IN')]);
		expect(await speak('', 'en', { synth, makeUtterance: make, defer: now })).toBe('empty');
	});
});
