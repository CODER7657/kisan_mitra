<script lang="ts">
	import { marked } from 'marked';
	import { onDestroy, onMount } from 'svelte';
	import { DEV_API_URL, readReply, resolveApiUrl } from '#lib/api.ts';
	import { formatDuration, loadingMessage } from '#lib/ui.ts';
	import { MAX_RECORDING_MS, shrinkPhoto, tooLargeMessage } from '#lib/upload.ts';
	import { NO_VOICE_MESSAGE, speak, type Lang } from '#lib/speech.ts';
	import { SKY_LABEL, skyForDay, type Sky } from '#lib/weather.ts';
	import Camera from 'lucide-svelte/icons/camera';
	import Cloud from 'lucide-svelte/icons/cloud';
	import CloudDrizzle from 'lucide-svelte/icons/cloud-drizzle';
	import CloudRain from 'lucide-svelte/icons/cloud-rain';
	import CloudRainWind from 'lucide-svelte/icons/cloud-rain-wind';
	import Mic from 'lucide-svelte/icons/mic';
	import Moon from 'lucide-svelte/icons/moon';
	import RotateCcw from 'lucide-svelte/icons/rotate-ccw';
	import Sprout from 'lucide-svelte/icons/sprout';
	import Square from 'lucide-svelte/icons/square';
	import Sun from 'lucide-svelte/icons/sun';
	import Volume2 from 'lucide-svelte/icons/volume-2';

	// One line icon per sky in the weather strip; 'unknown' gets a plain cloud, never a sun.
	const SKY_ICON: Record<Sky, typeof Sun> = {
		'heavy-rain': CloudRainWind,
		rain: CloudRain,
		showers: CloudDrizzle,
		'clear-day': Sun,
		'clear-night': Moon,
		unknown: Cloud
	};

	// Backend URL: set VITE_API_URL when building for production. Null means no backend is
	// configured, and the page says the service is unavailable instead of calling localhost.
	const API_URL = resolveApiUrl(
		import.meta.env.VITE_API_URL,
		import.meta.env.DEV ? DEV_API_URL : undefined
	);

	// A serverless backend may be cold after a quiet spell; start it while the farmer fills the form.
	onMount(() => {
		if (API_URL) fetch(`${API_URL}/health`).catch(() => {});
	});

	type Guess = { crop: string; condition: string; probability: number };
	type Result = {
		analysis: string;
		transcript: string;
		question: string;
		language: string;
		photo: { guesses: Guess[]; confident: boolean; crops_covered: string[] } | null;
		weather: {
			source: string;
			// Open-Meteo sends null for a value it does not have; the strip shows a dash.
			days: { date: string; rain_mm: number | null; rain_chance_pct: number | null }[];
		} | null;
		guard: { lines_removed: number; kvk_added: boolean };
	};

	// Undefined until the farmer picks a photo (bind:files).
	let imageFile: FileList | undefined;
	let question = '';
	let language = '';
	let useLocation = false;
	let audioBlob: Blob | null = null;
	let isRecording = false;
	let mediaRecorder: MediaRecorder | null = null;
	let recordStart = 0;

	let isLoading = false;
	let loadStart = 0;
	let now = Date.now();
	let ticker: ReturnType<typeof setInterval> | null = null;
	let controller: AbortController | null = null;
	let error: string | null = null;
	let result: Result | null = null;
	let analysisHtml = '';

	function startTicker() {
		now = Date.now();
		ticker ??= setInterval(() => (now = Date.now()), 500);
	}

	function stopTicker() {
		if (!isRecording && !isLoading && ticker) {
			clearInterval(ticker);
			ticker = null;
		}
	}

	onDestroy(() => {
		if (ticker) clearInterval(ticker);
	});

	async function startRecording() {
		error = null;
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			mediaRecorder = new MediaRecorder(stream);
			const chunks: BlobPart[] = [];
			mediaRecorder.ondataavailable = (event) => {
				chunks.push(event.data);
			};
			mediaRecorder.onstop = () => {
				audioBlob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
				stream.getTracks().forEach((t) => {
					t.stop();
				});
			};
			mediaRecorder.start();
			isRecording = true;
			recordStart = Date.now();
			startTicker();
			// Keep recordings short enough to upload; one minute is plenty for a question.
			const recorder = mediaRecorder;
			setTimeout(() => {
				if (recorder.state === 'recording') stopRecording();
			}, MAX_RECORDING_MS);
		} catch {
			error = 'Could not start recording. Please allow microphone access.';
		}
	}

	function stopRecording() {
		mediaRecorder?.stop();
		isRecording = false;
		stopTicker();
	}

	function discardRecording() {
		audioBlob = null;
	}

	function position(): Promise<GeolocationPosition | null> {
		return new Promise((resolve) => {
			// Absent outside a secure context (plain http), whatever the DOM types say.
			if ('geolocation' in navigator) {
				navigator.geolocation.getCurrentPosition(
					resolve,
					() => {
						resolve(null);
					},
					{ timeout: 8000 }
				);
			} else {
				resolve(null);
			}
		});
	}

	// The answer comes from a model, so any HTML in it is shown as text, never run.
	function safeMarkdown(md: string): string {
		const escaped = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
		return marked(escaped) as string;
	}

	let speaking = false;
	let speechNote = '';

	function stopSpeaking() {
		if ('speechSynthesis' in window) speechSynthesis.cancel();
		speaking = false;
	}

	async function readAloud() {
		if (speaking) {
			stopSpeaking();
			return;
		}
		speechNote = '';
		if (!result) return;
		if (!('speechSynthesis' in window)) {
			speechNote = 'This browser cannot read text aloud.';
			return;
		}
		const lang: Lang =
			result.language === 'gu' || result.language === 'hi' ? result.language : 'en';
		const outcome = await speak(result.analysis, lang, {
			synth: speechSynthesis,
			onEnd: () => (speaking = false)
		});
		if (outcome === 'speaking') speaking = true;
		else if (outcome === 'no-voice') speechNote = NO_VOICE_MESSAGE[lang];
	}

	async function handleSubmit() {
		error = null;
		result = null;
		if (!API_URL) return;
		if (isRecording) stopRecording();
		if (!audioBlob && !question.trim()) {
			error = 'Record your question or type it.';
			return;
		}
		isLoading = true;
		loadStart = Date.now();
		startTicker();
		const formData = new FormData();
		const photo = imageFile?.[0] ? await shrinkPhoto(imageFile[0]) : null;
		const tooLarge = tooLargeMessage((photo?.size ?? 0) + (audioBlob?.size ?? 0));
		if (tooLarge) {
			error = tooLarge;
			isLoading = false;
			stopTicker();
			return;
		}
		if (photo && imageFile?.[0]) {
			const name = photo === imageFile[0] ? imageFile[0].name : 'photo.jpg';
			formData.append('image_file', photo, name);
		}
		if (audioBlob) {
			const ext = audioBlob.type.includes('ogg')
				? 'ogg'
				: audioBlob.type.includes('mp4')
					? 'm4a'
					: 'webm';
			formData.append('audio_file', audioBlob, `question.${ext}`);
		}
		if (question.trim()) formData.append('question', question.trim());
		if (language) formData.append('language', language);
		if (useLocation) {
			const pos = await position();
			if (pos) {
				formData.append('lat', String(pos.coords.latitude));
				formData.append('lon', String(pos.coords.longitude));
			}
		}
		controller = new AbortController();
		const signal = controller.signal;
		try {
			const response = await fetch(`${API_URL}/analyze/`, {
				method: 'POST',
				body: formData,
				signal
			}).catch(() => {
				if (signal.aborted) throw new DOMException('cancelled', 'AbortError');
				// fetch rejects only when the backend can't be reached at all
				throw new Error('Could not reach the service. Check your connection and try again.');
			});
			// The backend's /analyze/ reply (backend/main.py), checked by the backend's tests.
			const data = (await readReply(response)) as Result;
			result = data;
			analysisHtml = safeMarkdown(data.analysis);
		} catch (e) {
			const err = e instanceof Error ? e : null;
			if (err?.name !== 'AbortError')
				error = err?.message || 'Something went wrong. Please try again.';
		} finally {
			controller = null;
			isLoading = false;
			stopTicker();
		}
	}

	function cancel() {
		controller?.abort();
	}

	function reset() {
		result = null;
		audioBlob = null;
		question = '';
		speechNote = '';
		// Not every browser has speech; a bare `speechSynthesis` would throw there.
		stopSpeaking();
	}
</script>

<svelte:head>
	<title>Kisan Mitra · Crop advice by voice</title>
	<meta
		name="description"
		content="Ask about your crop by voice or text in Gujarati, Hindi or English. Never gives chemical doses."
	/>
	<!-- The header band's colour (--rust in tokens.css); meta tags cannot read CSS variables. -->
	<meta name="theme-color" content="#8c2f1d" />
</svelte:head>

<div class="top">
	<div class="bar">
		<Sprout class="mark" size={28} strokeWidth={1.75} />
		<span class="brand">Kisan Mitra</span>
		<span class="tag">Crop advice by voice</span>
	</div>
</div>

<main class="page">
	<header class="intro">
		<h1>Ask about your crop.</h1>
		<p>Speak or type your question in Gujarati, Hindi or English. A photo of the plant helps.</p>
	</header>

	{#if !API_URL}
		<div class="notice error" role="alert">
			<strong>Service unavailable.</strong> This copy of Kisan Mitra is not connected to its server yet.
			Please try again later.
		</div>
	{:else if isLoading}
		<section class="panel loading" aria-live="polite" aria-busy="true">
			<div class="progress" aria-hidden="true"><span></span></div>
			<p class="loading-text">{loadingMessage(now - loadStart)}</p>
			<p class="muted small">{formatDuration(now - loadStart)} elapsed</p>
			<button type="button" class="btn secondary" on:click={cancel}>Cancel</button>
		</section>
	{:else if result}
		<section class="panel" aria-labelledby="answer-title">
			<h2 id="answer-title" class="section-title">Answer</h2>
			{#if result.transcript}
				<p class="said"><span class="label">You said</span>{result.transcript}</p>
			{/if}
			{#if result.photo}
				<div class="photo-check" class:unsure={!result.photo.confident}>
					<span class="label">Photo check</span>
					{#if result.photo.confident}
						{result.photo.guesses[0].crop}, {result.photo.guesses[0].condition}
						({Math.round(result.photo.guesses[0].probability * 100)}%). It can be wrong.
					{:else}
						Not sure. It only knows {result.photo.crops_covered.length} crops ({result.photo.crops_covered.join(
							', '
						)}), so the answer relies on your question.
					{/if}
				</div>
			{/if}
			<div class="markdown-content">
				<!-- eslint-disable-next-line svelte/no-at-html-tags -- safeMarkdown escapes the model's HTML first -->
				{@html analysisHtml}
			</div>
			{#if result.weather}
				{@const today = new Date()}
				<div class="weather">
					<span class="label"
						>Rain forecast <span class="muted">({result.weather.source})</span></span
					>
					<ul class="strip">
						{#each result.weather.days as d (d.date)}
							{@const sky = skyForDay(d, today)}
							{@const Icon = SKY_ICON[sky]}
							<li data-sky={sky}>
								<Icon class="sky-icon" size={28} strokeWidth={1.75} />
								<span class="visually-hidden">{SKY_LABEL[sky]}</span>
								<span class="date">{d.date}</span>
								<span class="mm">{d.rain_mm == null ? '–' : `${d.rain_mm} mm`}</span>
								<span class="muted pct"
									>{d.rain_chance_pct == null ? '–' : `${d.rain_chance_pct}%`}</span
								>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if result.guard.lines_removed > 0}
				<p class="muted small">
					Safety check removed {result.guard.lines_removed} line(s) that gave a chemical dose.
				</p>
			{/if}
			{#if speechNote}
				<p class="muted small" role="status">{speechNote}</p>
			{/if}
			<div class="actions">
				<button type="button" class="btn" on:click={readAloud}
					>{#if speaking}<Square size={22} />Stop reading{:else}<Volume2 size={22} />Read aloud{/if}</button
				>
				<button type="button" class="btn secondary" on:click={reset}
					><RotateCcw size={22} />Ask another question</button
				>
			</div>
		</section>
	{:else}
		<form on:submit|preventDefault={handleSubmit} class="panel form" novalidate>
			{#if error}
				<p class="notice error" role="alert">{error}</p>
			{/if}

			<fieldset class="step">
				<legend><span class="num">1</span>Your question</legend>
				<div class="record">
					{#if isRecording}
						<button type="button" class="btn rec on" on:click={stopRecording}>
							<Square class="rec-icon" size={20} />Stop recording
						</button>
						<span class="status" aria-live="polite"
							>Recording {formatDuration(now - recordStart)}</span
						>
					{:else}
						<button type="button" class="btn rec" on:click={startRecording}>
							<Mic class="rec-icon" size={22} />{audioBlob ? 'Record again' : 'Speak your question'}
						</button>
						{#if audioBlob}
							<span class="status ok">Recorded</span>
							<button type="button" class="link" on:click={discardRecording}>Remove</button>
						{/if}
					{/if}
				</div>
				<label class="field">
					<span>Or type it</span>
					<textarea
						bind:value={question}
						rows="3"
						placeholder="For example: the cotton leaves have turned yellow at the edges"></textarea>
				</label>
			</fieldset>

			<hr class="sep" />

			<fieldset class="step">
				<legend
					><span class="num">2</span>Photo of the crop <span class="muted">(optional)</span></legend
				>
				<input
					type="file"
					id="image"
					class="visually-hidden"
					accept="image/*"
					capture="environment"
					bind:files={imageFile}
				/>
				<div class="photo-row">
					<label for="image" class="btn secondary"
						><Camera size={22} />{imageFile?.[0] ? 'Change photo' : 'Take or choose photo'}</label
					>
					<span class="status">{imageFile?.[0]?.name || 'No photo'}</span>
				</div>
			</fieldset>

			<hr class="sep" />

			<fieldset class="step">
				<legend><span class="num">3</span>Options</legend>
				<label class="field">
					<span>Language</span>
					<select bind:value={language}>
						<option value="">Detect automatically</option>
						<option value="gu" lang="gu">ગુજરાતી</option>
						<option value="hi" lang="hi">हिन्दी</option>
						<option value="en">English</option>
					</select>
				</label>
				<label class="check">
					<input type="checkbox" bind:checked={useLocation} />
					<span>Use my location for the rain forecast</span>
				</label>
			</fieldset>

			<button type="submit" class="btn primary">Get advice</button>
			<p class="muted small">
				Kisan Mitra never gives pesticide or fertiliser doses. Confirm any chemical with your Krishi
				Vigyan Kendra (KVK).
			</p>
		</form>
	{/if}
</main>

<footer class="foot">
	<p>
		Advice is generated by AI and checked by fixed safety rules. It can be wrong; for anything
		serious, ask your KVK.
	</p>
</footer>

<style>
	/* Restrained Bohemian. Every colour, font and size comes from #lib/tokens.css. */

	/* Header band: rust with a low-contrast folk dot pattern, the only patterned area. */
	.top {
		background: var(--folk-dots), var(--rust);
		color: var(--sand);
		border-bottom: 4px solid var(--terracotta);
	}
	.bar {
		max-width: 720px;
		margin: 0 auto;
		padding: 0 20px;
		min-height: 64px;
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.bar :global(.mark) {
		color: var(--ochre);
		flex: none;
	}
	.brand {
		font-family: var(--font-heading);
		font-weight: 600;
		font-size: clamp(1.25rem, 1.15rem + 0.4vw, 1.5rem);
		letter-spacing: 0.01em;
	}
	.tag {
		margin-left: auto;
	}

	.page {
		max-width: 720px;
		margin: 0 auto;
		padding: 0 20px 24px;
	}
	.intro {
		padding: clamp(28px, 5vw, 48px) 0 24px;
	}
	h1 {
		font-size: var(--text-h1);
		line-height: 1.1;
		letter-spacing: -0.01em;
		margin: 0 0 14px;
	}
	/* A short terracotta rule under the title: decoration only, no text sits on it. */
	h1::after {
		content: '';
		display: block;
		width: 72px;
		height: 4px;
		margin-top: 14px;
		border-radius: 2px;
		background: var(--terracotta);
	}
	.intro p {
		margin: 0;
		color: var(--ink-soft);
		font-size: var(--text-lead);
		max-width: 36em;
	}

	/* Content surfaces are opaque paper, so the background grain never sits behind their text. */
	.panel {
		background: var(--paper);
		border: 1px solid var(--line);
		border-top: 4px solid var(--terracotta);
		border-radius: var(--radius);
		padding: clamp(20px, 4vw, 32px);
		box-shadow: var(--shadow);
	}
	.form {
		display: grid;
		gap: 28px;
	}

	.step {
		border: 0;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 14px;
		min-width: 0;
	}
	.sep {
		border: 0;
		border-top: 1px dashed var(--line);
		margin: 0;
	}
	legend {
		font-family: var(--font-heading);
		font-weight: 600;
		font-size: var(--text-h3);
		padding: 0;
		margin-bottom: 14px;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}
	legend .muted {
		font-family: var(--font-body);
		font-size: var(--text-body);
	}
	.num {
		display: inline-grid;
		place-items: center;
		width: 34px;
		height: 34px;
		border-radius: 50%;
		background: var(--ochre);
		color: var(--ink);
		font-family: var(--font-body);
		font-size: var(--text-body);
		font-weight: 600;
		flex: none;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		min-height: var(--touch);
		padding: 10px 22px;
		font-family: inherit;
		font-size: var(--text-button);
		font-weight: 600;
		line-height: 1.25;
		border-radius: var(--radius-small);
		border: 2px solid var(--cactus);
		background: var(--cactus);
		color: var(--paper);
		cursor: pointer;
		text-align: center;
	}
	.btn:hover {
		background: var(--cactus-deep);
		border-color: var(--cactus-deep);
	}
	.btn.secondary {
		background: var(--paper);
		color: var(--cactus);
		border-color: var(--cactus);
	}
	.btn.secondary:hover {
		background: var(--cactus-soft);
	}
	.btn.primary {
		width: 100%;
		min-height: 60px;
		font-size: var(--text-lead);
	}

	.record,
	.photo-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 12px 16px;
	}
	.btn.rec {
		background: var(--paper);
		color: var(--ink);
		border-color: var(--line-strong);
	}
	.btn.rec:hover {
		background: var(--ochre-soft);
	}
	.btn.rec :global(.rec-icon) {
		color: var(--rust);
		flex: none;
	}
	.btn.rec.on {
		border-color: var(--rust);
		color: var(--rust);
		background: var(--rust-soft);
	}
	.btn.rec.on :global(.rec-icon) {
		fill: currentColor;
	}
	.status {
		color: var(--ink-soft);
		font-variant-numeric: tabular-nums;
		overflow-wrap: anywhere;
	}
	.status.ok {
		color: var(--cactus);
		font-weight: 600;
	}
	.link {
		background: none;
		border: 0;
		padding: 8px 6px;
		min-height: var(--touch);
		color: var(--ink-soft);
		text-decoration: underline;
		text-underline-offset: 3px;
		font: inherit;
		cursor: pointer;
	}

	.field {
		display: grid;
		gap: 8px;
	}
	.field > span {
		color: var(--ink-soft);
	}
	textarea,
	select {
		width: 100%;
		font: inherit;
		color: var(--ink);
		background: var(--paper);
		border: 2px solid var(--line-strong);
		border-radius: var(--radius-small);
		padding: 12px 14px;
		min-height: var(--touch);
	}
	textarea {
		resize: vertical;
	}
	textarea::placeholder {
		color: var(--ink-soft);
		opacity: 1;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: var(--touch);
		cursor: pointer;
	}
	.check input {
		width: 24px;
		height: 24px;
		accent-color: var(--cactus);
		flex: none;
	}
	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	.visually-hidden:focus-visible + .photo-row .btn {
		outline: var(--focus);
		outline-offset: 3px;
	}

	.notice {
		margin: 0;
		padding: 14px 16px;
		border-radius: var(--radius-small);
		border: 1px solid var(--line);
	}
	.notice.error {
		color: var(--rust);
		background: var(--rust-soft);
		border-color: var(--rust);
		border-left-width: 6px;
	}

	.loading {
		text-align: center;
		display: grid;
		gap: 12px;
		justify-items: center;
		padding: 40px 24px;
	}
	.progress {
		width: 100%;
		max-width: 320px;
		height: 6px;
		border-radius: 3px;
		background: var(--ochre-soft);
		overflow: hidden;
		margin-bottom: 8px;
	}
	.progress span {
		display: block;
		width: 35%;
		height: 100%;
		background: var(--terracotta);
		border-radius: 3px;
	}
	.loading-text {
		margin: 0;
		font-weight: 600;
		max-width: 420px;
	}

	.section-title {
		font-size: var(--text-h2);
		line-height: 1.2;
		margin: 0 0 16px;
	}
	.label {
		display: block;
		font-weight: 600;
		color: var(--ink-soft);
		margin-bottom: 4px;
	}
	.said {
		margin: 0 0 16px;
		padding-bottom: 16px;
		border-bottom: 1px dashed var(--line);
	}
	.photo-check {
		padding: 12px 16px;
		border-radius: var(--radius-small);
		background: var(--cactus-soft);
		margin-bottom: 16px;
	}
	.photo-check.unsure {
		background: var(--ochre-soft);
	}
	.markdown-content {
		overflow-wrap: anywhere;
	}
	.markdown-content :global(h1),
	.markdown-content :global(h2),
	.markdown-content :global(h3) {
		font-size: var(--text-h3);
		line-height: 1.3;
		margin: 20px 0 8px;
	}
	.markdown-content :global(ul),
	.markdown-content :global(ol) {
		padding-left: 24px;
	}
	.markdown-content :global(li) {
		margin: 6px 0;
	}
	.markdown-content :global(li::marker) {
		color: var(--terracotta);
	}
	.markdown-content :global(table) {
		border-collapse: collapse;
		display: block;
		overflow-x: auto;
	}
	.markdown-content :global(th),
	.markdown-content :global(td) {
		border: 1px solid var(--line);
		padding: 6px 10px;
	}

	/* Weather strip: one entry per day, each led by a sun, moon or rain line icon. */
	.weather {
		margin: 24px 0 8px;
		padding-top: 18px;
		border-top: 1px dashed var(--line);
	}
	.strip {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.strip li {
		display: grid;
		grid-template-columns: 28px 1fr auto auto;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		white-space: nowrap;
		border-radius: var(--radius-small);
		background: var(--sand);
		font-variant-numeric: tabular-nums;
	}
	.strip .mm,
	.strip .pct {
		text-align: right;
	}
	.strip :global(.sky-icon) {
		color: var(--ink-soft);
	}
	.strip li[data-sky='heavy-rain'] :global(.sky-icon),
	.strip li[data-sky='rain'] :global(.sky-icon),
	.strip li[data-sky='showers'] :global(.sky-icon) {
		color: var(--cactus);
	}
	.strip li[data-sky='clear-day'] :global(.sky-icon) {
		color: var(--rust);
	}
	.strip li[data-sky='clear-night'] :global(.sky-icon) {
		color: var(--ink);
	}
	@media (min-width: 640px) {
		.strip {
			grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		}
		.strip li {
			grid-template-columns: 1fr auto;
			grid-template-areas: 'icon pct' 'date date' 'mm mm';
			gap: 2px 8px;
			padding: 14px 16px;
		}
		.strip :global(.sky-icon) {
			grid-area: icon;
		}
		.strip .date {
			grid-area: date;
			margin-top: 6px;
		}
		.strip .mm {
			grid-area: mm;
			text-align: left;
			font-weight: 600;
		}
		.strip .pct {
			grid-area: pct;
		}
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
		margin-top: 28px;
	}

	.muted {
		color: var(--ink-soft);
		font-weight: 400;
	}
	.small {
		line-height: 1.5;
		margin: 0;
	}
	.foot {
		max-width: 720px;
		margin: 0 auto;
		padding: 8px 20px 40px;
		color: var(--ink-soft);
	}

	@media (max-width: 520px) {
		.tag {
			display: none;
		}
		.bar,
		.page,
		.foot {
			padding-left: 16px;
			padding-right: 16px;
		}
		.actions .btn,
		.record .btn.rec,
		.photo-row .btn {
			flex: 1 1 100%;
		}
	}

	/* Motion only for people who have not asked for less. */
	@media (prefers-reduced-motion: no-preference) {
		.btn,
		textarea,
		select {
			transition:
				background-color 0.15s,
				border-color 0.15s;
		}
		.progress span {
			animation: slide 1.4s ease-in-out infinite;
		}
		.btn.rec.on :global(.rec-icon) {
			animation: pulse 1.2s ease-in-out infinite;
		}
	}
	@keyframes slide {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(290%);
		}
	}
	@keyframes pulse {
		50% {
			opacity: 0.35;
		}
	}
</style>
