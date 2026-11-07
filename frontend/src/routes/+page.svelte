<script lang="ts">
	import { marked } from 'marked';
	import { onDestroy, onMount } from 'svelte';
	import { readReply, resolveApiUrl } from '$lib/api';
	import { formatDuration, loadingMessage } from '$lib/ui';
	import { MAX_RECORDING_MS, shrinkPhoto, tooLargeMessage } from '$lib/upload';

	// Backend URL: set VITE_API_URL when building for production. Null means no backend is
	// configured, and the page says the service is unavailable instead of calling localhost.
	const API_URL = resolveApiUrl(import.meta.env.VITE_API_URL, import.meta.env.DEV);

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
		weather: { source: string; days: { date: string; rain_mm: number; rain_chance_pct: number }[] } | null;
		guard: { lines_removed: number; kvk_added: boolean };
	};

	let imageFile: FileList;
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

	onDestroy(() => ticker && clearInterval(ticker));

	async function startRecording() {
		error = null;
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			mediaRecorder = new MediaRecorder(stream);
			const chunks: BlobPart[] = [];
			mediaRecorder.ondataavailable = (event) => chunks.push(event.data);
			mediaRecorder.onstop = () => {
				audioBlob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
				stream.getTracks().forEach((t) => t.stop());
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
		} catch (err) {
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
		return new Promise((resolve) =>
			navigator.geolocation
				? navigator.geolocation.getCurrentPosition(resolve, () => resolve(null), { timeout: 8000 })
				: resolve(null)
		);
	}

	// The answer comes from a model, so any HTML in it is shown as text, never run.
	function safeMarkdown(md: string): string {
		const escaped = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
		return marked(escaped) as string;
	}

	function readAloud() {
		if (!result || !('speechSynthesis' in window)) return;
		const u = new SpeechSynthesisUtterance(result.analysis.replace(/[*#|_>]/g, ''));
		u.lang = { gu: 'gu-IN', hi: 'hi-IN' }[result.language] ?? 'en-IN';
		speechSynthesis.cancel();
		speechSynthesis.speak(u);
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
			const ext = audioBlob.type.includes('ogg') ? 'ogg' : audioBlob.type.includes('mp4') ? 'm4a' : 'webm';
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
			const response = await fetch(`${API_URL}/analyze/`, { method: 'POST', body: formData, signal }).catch(() => {
				if (signal.aborted) throw new DOMException('cancelled', 'AbortError');
				// fetch rejects only when the backend can't be reached at all
				throw new Error('Could not reach the service. Check your connection and try again.');
			});
			const data = await readReply(response);
			result = data;
			analysisHtml = safeMarkdown(data.analysis);
		} catch (e: any) {
			if (e?.name !== 'AbortError') error = e.message || 'Something went wrong. Please try again.';
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
		speechSynthesis?.cancel();
	}
</script>

<svelte:head>
	<title>Kisan Mitra · Crop advice by voice</title>
	<meta name="description" content="Ask about your crop by voice or text in Gujarati, Hindi or English. Never gives chemical doses." />
	<meta name="theme-color" content="#f7f6f1" />
</svelte:head>

<div class="top">
	<div class="bar">
		<span class="mark" aria-hidden="true"></span>
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
						Not sure. It only knows {result.photo.crops_covered.length} crops
						({result.photo.crops_covered.join(', ')}), so the answer relies on your question.
					{/if}
				</div>
			{/if}
			<div class="markdown-content">
				{@html analysisHtml}
			</div>
			{#if result.weather}
				<div class="weather">
					<span class="label">Rain forecast <span class="muted">({result.weather.source})</span></span>
					<ul>
						{#each result.weather.days as d}
							<li><span>{d.date}</span><span>{d.rain_mm} mm</span><span class="muted">{d.rain_chance_pct}%</span></li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if result.guard.lines_removed > 0}
				<p class="muted small">Safety check removed {result.guard.lines_removed} line(s) that gave a chemical dose.</p>
			{/if}
			<div class="actions">
				<button type="button" class="btn" on:click={readAloud}>Read aloud</button>
				<button type="button" class="btn secondary" on:click={reset}>Ask another question</button>
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
							<span class="dot" aria-hidden="true"></span>Stop recording
						</button>
						<span class="status" aria-live="polite">Recording {formatDuration(now - recordStart)}</span>
					{:else}
						<button type="button" class="btn rec" on:click={startRecording}>
							<span class="dot" aria-hidden="true"></span>{audioBlob ? 'Record again' : 'Speak your question'}
						</button>
						{#if audioBlob}
							<span class="status ok">Recorded</span>
							<button type="button" class="link" on:click={discardRecording}>Remove</button>
						{/if}
					{/if}
				</div>
				<label class="field">
					<span>Or type it</span>
					<textarea bind:value={question} rows="3" placeholder="For example: the cotton leaves have turned yellow at the edges"></textarea>
				</label>
			</fieldset>

			<hr class="sep" />

			<fieldset class="step">
				<legend><span class="num">2</span>Photo of the crop <span class="muted">(optional)</span></legend>
				<input type="file" id="image" class="visually-hidden" accept="image/*" capture="environment" bind:files={imageFile} />
				<div class="photo-row">
					<label for="image" class="btn secondary">{imageFile?.[0] ? 'Change photo' : 'Take or choose photo'}</label>
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
	<p>Advice is generated by AI and checked by fixed safety rules. It can be wrong; for anything serious, ask your KVK.</p>
</footer>

<style>
	:global(:root) {
		--bg: #f7f6f1;
		--panel: #ffffff;
		--ink: #1d2a22;
		--muted: #5e6a61;
		--line: #e3e1d8;
		--accent: #2f5d3a;
		--accent-ink: #ffffff;
		--accent-soft: #eaf1eb;
		--ochre: #8a6a12;
		--ochre-soft: #faf4e2;
		--danger: #9b2c2c;
		--danger-soft: #fbefee;
	}
	:global(*) {
		box-sizing: border-box;
	}
	:global(body) {
		margin: 0;
		background: var(--bg);
		color: var(--ink);
		font: 17px/1.55 -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans', 'Noto Sans Gujarati',
			'Noto Sans Devanagari', 'Helvetica Neue', Arial, sans-serif;
		-webkit-text-size-adjust: 100%;
	}
	:global(:focus-visible) {
		outline: 3px solid var(--accent);
		outline-offset: 2px;
	}

	.top {
		background: var(--panel);
		border-bottom: 1px solid var(--line);
	}
	.bar {
		max-width: 680px;
		margin: 0 auto;
		padding: 0 20px;
		height: 56px;
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.mark {
		width: 14px;
		height: 14px;
		border-radius: 3px;
		background: var(--accent);
	}
	.brand {
		font-weight: 700;
		letter-spacing: 0.01em;
	}
	.tag {
		color: var(--muted);
		font-size: 14px;
		margin-left: 4px;
	}

	.page {
		max-width: 680px;
		margin: 0 auto;
		padding: 0 20px 24px;
	}
	.intro {
		padding: 32px 0 20px;
	}
	h1 {
		font-size: clamp(28px, 6vw, 36px);
		line-height: 1.15;
		letter-spacing: -0.02em;
		margin: 0 0 8px;
	}
	.intro p {
		margin: 0;
		color: var(--muted);
	}

	.panel {
		background: var(--panel);
		border: 1px solid var(--line);
		border-radius: 10px;
		padding: 24px;
	}
	.form {
		display: grid;
		gap: 24px;
	}

	.step {
		border: 0;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 12px;
		min-width: 0;
	}
	.sep {
		border: 0;
		border-top: 1px solid var(--line);
		margin: 0;
	}
	legend {
		font-weight: 700;
		padding: 0;
		margin-bottom: 12px;
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.num {
		display: inline-grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 50%;
		background: var(--accent-soft);
		color: var(--accent);
		font-size: 14px;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		min-height: 48px;
		padding: 0 20px;
		font-family: inherit;
		font-size: 16px;
		font-weight: 600;
		line-height: 1.2;
		border-radius: 8px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--accent-ink);
		cursor: pointer;
		text-align: center;
		transition: background-color 0.15s, border-color 0.15s;
	}
	.btn:hover {
		background: #264d30;
	}
	.btn.secondary {
		background: var(--panel);
		color: var(--accent);
		border-color: #c9d6cc;
	}
	.btn.secondary:hover {
		background: var(--accent-soft);
	}
	.btn.primary {
		width: 100%;
		min-height: 56px;
		font-size: 18px;
	}

	.record,
	.photo-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 12px 16px;
	}
	.btn.rec {
		background: var(--panel);
		color: var(--ink);
		border-color: #cdd3cd;
	}
	.btn.rec:hover {
		background: #f3f4f1;
	}
	.btn.rec .dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--danger);
	}
	.btn.rec.on {
		border-color: var(--danger);
		color: var(--danger);
		background: var(--danger-soft);
	}
	.btn.rec.on .dot {
		border-radius: 2px;
		animation: pulse 1.2s ease-in-out infinite;
	}
	@keyframes pulse {
		50% {
			opacity: 0.35;
		}
	}
	.status {
		color: var(--muted);
		font-size: 15px;
		font-variant-numeric: tabular-nums;
		overflow-wrap: anywhere;
	}
	.status.ok {
		color: var(--accent);
		font-weight: 600;
	}
	.link {
		background: none;
		border: 0;
		padding: 8px 4px;
		min-height: 44px;
		color: var(--muted);
		text-decoration: underline;
		font: inherit;
		font-size: 15px;
		cursor: pointer;
	}

	.field {
		display: grid;
		gap: 6px;
	}
	.field > span {
		font-size: 15px;
		color: var(--muted);
	}
	textarea,
	select {
		width: 100%;
		font: inherit;
		color: var(--ink);
		background: var(--panel);
		border: 1px solid #cdd3cd;
		border-radius: 8px;
		padding: 12px 14px;
		min-height: 48px;
	}
	textarea {
		resize: vertical;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 48px;
		cursor: pointer;
	}
	.check input {
		width: 22px;
		height: 22px;
		accent-color: var(--accent);
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
		outline: 3px solid var(--accent);
		outline-offset: 2px;
	}

	.notice {
		margin: 0;
		padding: 14px 16px;
		border-radius: 8px;
		border: 1px solid var(--line);
	}
	.notice.error {
		color: var(--danger);
		background: var(--danger-soft);
		border-color: #ebc9c9;
	}

	.loading {
		text-align: center;
		display: grid;
		gap: 10px;
		justify-items: center;
		padding: 40px 24px;
	}
	.progress {
		width: 100%;
		max-width: 320px;
		height: 4px;
		border-radius: 2px;
		background: var(--accent-soft);
		overflow: hidden;
		margin-bottom: 8px;
	}
	.progress span {
		display: block;
		width: 35%;
		height: 100%;
		background: var(--accent);
		border-radius: 2px;
		animation: slide 1.4s ease-in-out infinite;
	}
	@keyframes slide {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(290%);
		}
	}
	.loading-text {
		margin: 0;
		font-weight: 600;
		max-width: 420px;
	}

	.section-title {
		font-size: 14px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--muted);
		margin: 0 0 16px;
	}
	.label {
		display: block;
		font-size: 13px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--muted);
		margin-bottom: 4px;
	}
	.said {
		margin: 0 0 16px;
		padding-bottom: 16px;
		border-bottom: 1px solid var(--line);
	}
	.photo-check {
		padding: 12px 14px;
		border-radius: 8px;
		background: var(--accent-soft);
		margin-bottom: 16px;
	}
	.photo-check.unsure {
		background: var(--ochre-soft);
	}
	.photo-check.unsure .label {
		color: var(--ochre);
	}
	.markdown-content {
		overflow-wrap: anywhere;
	}
	.markdown-content :global(h1),
	.markdown-content :global(h2),
	.markdown-content :global(h3) {
		font-size: 18px;
		margin: 20px 0 8px;
	}
	.markdown-content :global(ul),
	.markdown-content :global(ol) {
		padding-left: 22px;
	}
	.markdown-content :global(li) {
		margin: 4px 0;
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
	.weather {
		margin: 20px 0 8px;
		padding-top: 16px;
		border-top: 1px solid var(--line);
	}
	.weather ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 4px;
	}
	.weather li {
		display: grid;
		grid-template-columns: 1fr auto 56px;
		gap: 12px;
		font-variant-numeric: tabular-nums;
	}
	.weather li span:not(:first-child) {
		text-align: right;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
		margin-top: 24px;
	}

	.muted {
		color: var(--muted);
		font-weight: 400;
	}
	.small {
		font-size: 14px;
		margin: 0;
	}
	.foot {
		max-width: 680px;
		margin: 0 auto;
		padding: 8px 20px 40px;
		color: var(--muted);
		font-size: 14px;
	}

	@media (max-width: 520px) {
		.tag {
			display: none;
		}
		.panel {
			padding: 20px 16px;
		}
		.actions .btn,
		.record .btn.rec,
		.photo-row .btn {
			flex: 1 1 100%;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.progress span,
		.btn.rec.on .dot {
			animation: none;
		}
	}
</style>
