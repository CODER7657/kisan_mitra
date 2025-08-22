<!-- frontend/src/routes/+page.svelte -->

<script lang="ts">
	import { marked } from 'marked';

	// --- State Management ---
	// These variables will hold the state of our application
	let videoFile: FileList;
	let audioFile: FileList;
	let historyFile: FileList;

	let isLoading = false; // To show a loading spinner
	let error: string | null = null; // To display any errors
	let analysisResult: string | null = null; // To store the AI's response

	// --- Form Submission Handler ---
	async function handleSubmit() {
		// 1. Reset state and validate inputs
		isLoading = true;
		error = null;
		analysisResult = null;

		if (!videoFile?.[0] || !audioFile?.[0] || !historyFile?.[0]) {
			error = 'Please select all three files before analyzing.';
			isLoading = false;
			return;
		}

		// 2. Prepare form data for the backend
		const formData = new FormData();
		formData.append('video_file', videoFile[0]);
		formData.append('audio_file', audioFile[0]);
		formData.append('history_file', historyFile[0]);

		// 3. Send data to the FastAPI backend
		try {
			// We'll use localhost for local testing. This will be changed for deployment.
			const response = await fetch('http://127.0.0.1:8000/analyze/', {
				method: 'POST',
				body: formData
			});

			if (!response.ok) {
				// Handle server-side errors
				const errorData = await response.json();
				throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
			}

			const data = await response.json();

			// 4. Update the UI with the result
			// We use the 'marked' library to convert the Markdown response to HTML
			analysisResult = marked(data.analysis) as string;

		} catch (e: any) {
			console.error('An error occurred during fetch:', e);
			error = e.message || 'An unknown error occurred. Please check the console.';
		} finally {
			// 5. Stop the loading indicator
			isLoading = false;
		}
	}
</script>

<main class="container">
	<header>
		<h1>🌾 Kisan Mitra AI</h1>
		<p>Your AI-powered agricultural diagnostic assistant.</p>
	</header>

	{#if isLoading}
		<!-- Loading State -->
		<div class="loading-container">
			<div class="spinner" />
			<p>Analyzing your data... This may take a moment.</p>
		</div>
	{:else if analysisResult}
		<!-- Result Display State -->
		<div class="results-card">
			<h2>Analysis Complete</h2>
			<div class="markdown-content">
				{@html analysisResult}
			</div>
			<button on:click={() => (analysisResult = null)}>Start New Analysis</button>
		</div>
	{:else}
		<!-- Initial Form State -->
		<form on:submit|preventDefault={handleSubmit} class="upload-form">
			{#if error}
				<p class="error-message">{error}</p>
			{/if}

			<div class="file-input-group">
				<label for="video">1. Upload Crop Video</label>
				<input type="file" id="video" accept="video/*" bind:files={videoFile} required />
				<span>{videoFile?.[0]?.name || 'No file selected'}</span>
			</div>

			<div class="file-input-group">
				<label for="audio">2. Upload Audio Query</label>
				<input type="file" id="audio" accept="audio/*" bind:files={audioFile} required />
				<span>{audioFile?.[0]?.name || 'No file selected'}</span>
			</div>

			<div class="file-input-group">
				<label for="history">3. Upload Farm History (.txt)</label>
				<input type="file" id="history" accept=".txt" bind:files={historyFile} required />
				<span>{historyFile?.[0]?.name || 'No file selected'}</span>
			</div>

-
			<button type="submit" disabled={isLoading}>Analyze Farm Data</button>
		</form>
	{/if}
</main>

<!-- Basic Styling -->
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

</style>