<script lang="ts">
	import { marked } from 'marked';
	import { onMount } from 'svelte';
	import { readReply, resolveApiUrl } from '$lib/api';

	// Backend URL: set VITE_API_URL when building for production. Null means no backend is
	// configured, and the page says the service is unavailable instead of calling localhost.
	const API_URL = resolveApiUrl(import.meta.env.VITE_API_URL, import.meta.env.DEV);

	// A free-tier backend sleeps when idle; start waking it while the farmer fills the form.
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

	let isLoading = false;
	let error: string | null = null;
	let result: Result | null = null;
	let analysisHtml = '';

	async function startRecording() {
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
		} catch (err) {
			error = 'Could not start recording. Please allow microphone access.';
		}
	}

	function stopRecording() {
		mediaRecorder?.stop();
		isRecording = false;
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
		if (!audioBlob && !question.trim()) {
			error = 'Record your question or type it.';
			return;
		}
		isLoading = true;
		const formData = new FormData();
		if (imageFile?.[0]) formData.append('image_file', imageFile[0]);
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
		try {
			const response = await fetch(`${API_URL}/analyze/`, { method: 'POST', body: formData }).catch(() => {
				// fetch rejects only when the backend can't be reached at all
				throw new Error('Could not reach the service. Check your connection and try again.');
			});
			const data = await readReply(response);
			result = data;
			analysisHtml = safeMarkdown(data.analysis);
		} catch (e: any) {
			error = e.message || 'Something went wrong. Please try again.';
		} finally {
			isLoading = false;
		}
	}

	function reset() {
		result = null;
		audioBlob = null;
		question = '';
		speechSynthesis?.cancel();
	}
</script>

<main class="container">
	<header>
		<h1>🌾 Kisan Mitra AI</h1>
		<p>Ask about your crop by voice or text, in Gujarati, Hindi or English. A photo helps.</p>
	</header>

	{#if !API_URL}
		<div class="error-message" role="alert">
			<strong>Service unavailable.</strong> This copy of Kisan Mitra is not connected to its server yet.
			Please try again later.
		</div>
	{:else if isLoading}
		<div class="loading-container">
			<div class="spinner"></div>
			<p>Working on your answer... The first question after a quiet spell can take up to a minute.</p>
		</div>
	{:else if result}
		<div class="results-card">
			{#if result.transcript}
				<p class="meta"><strong>You said:</strong> {result.transcript}</p>
			{/if}
			{#if result.photo}
				<div class="photo-check" class:unsure={!result.photo.confident}>
					<strong>Automatic photo check:</strong>
					{#if result.photo.confident}
						{result.photo.guesses[0].crop}, {result.photo.guesses[0].condition}
						({Math.round(result.photo.guesses[0].probability * 100)}%). It can be wrong.
					{:else}
						not sure. It only knows {result.photo.crops_covered.length} crops
						({result.photo.crops_covered.join(', ')}), so the answer relies on your question.
					{/if}
				</div>
			{/if}
			<div class="markdown-content">
				{@html analysisHtml}
			</div>
			{#if result.weather}
				<p class="meta">
					Weather ({result.weather.source}):
					{#each result.weather.days as d}
						<span class="day">{d.date}: rain {d.rain_mm} mm ({d.rain_chance_pct}%)</span>
					{/each}
				</p>
			{/if}
			{#if result.guard.lines_removed > 0}
				<p class="meta">Safety check removed {result.guard.lines_removed} line(s) that gave a chemical dose.</p>
			{/if}
			<div class="actions">
				<button type="button" on:click={readAloud}>🔊 Read aloud</button>
				<button type="button" class="secondary" on:click={reset}>Ask another question</button>
			</div>
		</div>
	{:else}
		<form on:submit|preventDefault={handleSubmit} class="upload-form">
			{#if error}
				<p class="error-message">{error}</p>
			{/if}

			<div class="file-input-group">
				<label for="audio">1. Speak your question</label>
				{#if isRecording}
					<button type="button" on:click={stopRecording}>Stop recording</button>
				{:else}
					<button type="button" on:click={startRecording}>Start recording</button>
				{/if}
				<span>{audioBlob ? 'Recorded' : 'Nothing recorded yet'}</span>
				<textarea bind:value={question} rows="2" placeholder="...or type it here"></textarea>
			</div>

			<div class="file-input-group">
				<label for="image">2. Add a photo of the crop (optional)</label>
				<input type="file" id="image" accept="image/*" capture="environment" bind:files={imageFile} />
				<label for="image" class="pick">Choose photo</label>
				<span>{imageFile?.[0]?.name || 'No photo'}</span>
			</div>

			<div class="options">
				<label>
					Language
					<select bind:value={language}>
						<option value="">Detect</option>
						<option value="gu">ગુજરાતી</option>
						<option value="hi">हिन्दी</option>
						<option value="en">English</option>
					</select>
				</label>
				<label><input type="checkbox" bind:checked={useLocation} /> Use my location for the weather</label>
			</div>

			<button type="submit">Get advice</button>
			<p class="note">
				Kisan Mitra never gives pesticide or fertiliser doses. Confirm any chemical with your Krishi
				Vigyan Kendra (KVK).
			</p>
		</form>
	{/if}
</main>

<style>
	:global(body) {
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell,
			'Open Sans', 'Helvetica Neue', sans-serif;
		background-color: #f0f2f5;
		color: #333;
		margin: 0;
		display: flex;
		justify-content: center;
		align-items: flex-start;
		min-height: 100vh;
		padding: 2rem;
	}

	.container {
		width: 100%;
		max-width: 700px;
		background: white;
		padding: 2rem 3rem;
		border-radius: 16px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
	}

	header {
		text-align: center;
		margin-bottom: 2rem;
		border-bottom: 1px solid #e0e0e0;
		padding-bottom: 1.5rem;
	}

	h1 {
		color: #2c5e2e;
		margin: 0;
	}

	.upload-form {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.file-input-group {
		border: 2px dashed #ccc;
		border-radius: 8px;
		padding: 1.5rem;
		text-align: center;
		transition: border-color 0.2s;
	}

	.file-input-group:hover {
		border-color: #2c5e2e;
	}

	.file-input-group label {
		font-weight: bold;
		display: block;
		margin-bottom: 0.5rem;
	}

	.file-input-group input {
		width: 0.1px;
		height: 0.1px;
		opacity: 0;
		overflow: hidden;
		position: absolute;
		z-index: -1;
	}

    .file-input-group span {
        font-style: italic;
        color: #666;
        font-size: 0.9rem;
    }

	button {
		padding: 1rem;
		font-size: 1.1rem;
		font-weight: bold;
		color: white;
		background-color: #4caf50;
		border: none;
		border-radius: 8px;
		cursor: pointer;
		transition: background-color 0.2s;
	}

	button:hover {
		background-color: #45a049;
	}

	button:disabled {
		background-color: #ccc;
		cursor: not-allowed;
	}

	.loading-container {
		text-align: center;
		padding: 4rem 0;
	}

	.spinner {
		border: 6px solid #f3f3f3;
		border-top: 6px solid #4caf50;
		border-radius: 50%;
		width: 50px;
		height: 50px;
		animation: spin 1s linear infinite;
		margin: 0 auto 1rem;
	}

	@keyframes spin {
		0% {
			transform: rotate(0deg);
		}
		100% {
			transform: rotate(360deg);
		}
	}

	.error-message {
		color: #d32f2f;
		background-color: #ffebee;
		border: 1px solid #d32f2f;
		padding: 1rem;
		border-radius: 8px;
		text-align: center;
	}

	.results-card {
		padding: 2rem;
		background-color: #f9f9f9;
		border-radius: 8px;
		border: 1px solid #e0e0e0;
	}
    
    .markdown-content :global(h1), .markdown-content :global(h2), .markdown-content :global(h3) {
        color: #2c5e2e;
        border-bottom: 1px solid #ddd;
        padding-bottom: 0.3em;
    }

    .markdown-content :global(ul) {
        line-height: 1.6;
    }

	textarea, select {
		width: 100%;
		box-sizing: border-box;
		margin-top: 0.75rem;
		padding: 0.6rem;
		font-size: 1rem;
		border: 1px solid #ccc;
		border-radius: 8px;
		font-family: inherit;
	}

	.pick {
		display: inline-block;
		padding: 0.5rem 1rem;
		background: #e8f5e9;
		border-radius: 8px;
		cursor: pointer;
	}

	.options {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.note, .meta {
		font-size: 0.9rem;
		color: #555;
	}

	.photo-check {
		padding: 0.75rem 1rem;
		border-radius: 8px;
		background: #e8f5e9;
		margin-bottom: 1rem;
	}

	.photo-check.unsure {
		background: #fff8e1;
	}

	.day {
		margin-right: 0.75rem;
		white-space: nowrap;
	}

	.actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin-top: 1rem;
	}

	button.secondary {
		background-color: #607d8b;
	}

	@media (max-width: 600px) {
		:global(body) {
			padding: 0.5rem;
		}
		.container {
			padding: 1.25rem 1rem;
		}
	}
</style>

