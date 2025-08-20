
<script lang="ts">
  import { supabase } from '$lib/supabaseClient'; // Import our Supabase client

  // State variables to hold user files and app status
  let videoFile: FileList;
  let audioFile: FileList;
  let textFile: FileList;
  
  let isLoading = false;
  let analysisResult = '';
  let errorMessage = '';
  let loadingMessage = '';

  // Main function triggered by the button click
  async function handleSubmit() {
    // 1. Validate that all files are selected
    if (!videoFile?.[0] || !audioFile?.[0] || !textFile?.[0]) {
      errorMessage = 'Please select all three files before analyzing.';
      return;
    }

    // 2. Reset the UI state and start loading
    isLoading = true;
    analysisResult = '';
    errorMessage = '';

    // Helper function to upload a single file DIRECTLY to Supabase from the browser
    const uploadFile = async (file: File, folder: string) => {
  loadingMessage = `Uploading ${file.name}...`;
  const uniqueFileName = `${folder}/${Date.now()}-${file.name}`;

      // Use the supabase client to upload the file
      const { error } = await supabase.storage
        .from('media_uploads') // Our public bucket
        .upload(uniqueFileName, file);

      if (error) {
        throw new Error(`Failed to upload ${file.name}: ${error.message}`);
      }

      // If successful, get the public URL for the file
      const { data } = supabase.storage
        .from('media_uploads')
        .getPublicUrl(uniqueFileName);
      
      return data.publicUrl;
    };

    try {
      // 3. Upload all files directly to Supabase and get their public URLs
      const videoUploadUrl = await uploadFile(videoFile[0], 'videos');
      const audioUploadUrl = await uploadFile(audioFile[0], 'audio');
      const textUploadUrl = await uploadFile(textFile[0], 'text');

      loadingMessage = '🧠 AI is analyzing your files... This may take a moment.';

      // 4. Call our /api/analyze endpoint with the new URLs
      //    This request is small and will not hit the Vercel limit.
  const analysisResponse = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoUrl: videoUploadUrl,
          audioUrl: audioUploadUrl,
          farmHistoryUrl: textUploadUrl,
        }),
      });

if (!analysisResponse.ok) {
  const errorData = await analysisResponse.json().catch(() => ({ error: 'Analysis failed with no details.' }));
  throw new Error(`${errorData.error} The AI analysis failed.`);
      }
      
      const finalData = await analysisResponse.json();
      analysisResult = finalData.result; // Display the AI's response

    } catch (error: any) {
      // 5. Catch and display any errors
      errorMessage = error.message;
    } finally {
      // 6. Stop the loading indicator
      isLoading = false;
      loadingMessage = '';
    }
  }
</script>

<main>
  <div class="container">
    <header>
      <h1>🌾 Kisan Mitra AI 🌾</h1>
      <p>Your AI-powered farming assistant. Upload a video of your plant, an audio query in Hindi, and your farm history to get expert advice.</p>
    </header>

    <div class="upload-section">
      <div class="upload-box">
        <label for="video-upload">1. Upload Plant Video</label>
        <input type="file" id="video-upload" accept="video/*" bind:files={videoFile} />
      </div>
      <div class="upload-box">
        <label for="audio-upload">2. Upload Audio Query (Hindi)</label>
        <input type="file" id="audio-upload" accept="audio/*" bind:files={audioFile} />
      </div>
      <div class="upload-box">
        <label for="text-upload">3. Upload Farm History (.txt)</label>
        <input type="file" id="text-upload" accept=".txt" bind:files={textFile} />
      </div>
    </div>

    <button class="submit-button" on:click={handleSubmit} disabled={isLoading}>
      {#if isLoading}Analyzing...{:else}Analyze and Get Advice{/if}
    </button>

  {#if isLoading || analysisResult || errorMessage}
      <div class="results-section">
        {#if isLoading}
          <div class="loading-indicator">
            <div class="spinner"></div>
            <p>{loadingMessage}</p>
          </div>
        {/if}

        {#if analysisResult && !isLoading}
          <h2>AI Analysis & Recommendations</h2>
          <pre>{analysisResult}</pre>
        {/if}

        {#if errorMessage}
          <p class="error">Error: {errorMessage}</p>
        {/if}
      </div>
    {/if}
  </div>
</main>


<style>
  :root {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
      Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  }
  main {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background-color: #f0fdf4;
  }
  .container {
    width: 90%;
    max-width: 600px;
    background: #ffffff;
    padding: 2rem;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    text-align: center;
  }
  header h1 {
    color: #166534;
  }
  .upload-section {
    margin: 2rem 0;
    display: grid;
    gap: 1.5rem;
  }
  .upload-box {
    border: 2px dashed #9ca3af;
    padding: 1rem;
    border-radius: 8px;
  }
  .upload-box label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #374151;
  }
  .submit-button {
    background-color: #22c55e;
    color: white;
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 8px;
    font-size: 1.1rem;
    font-weight: bold;
    cursor: pointer;
    width: 100%;
    transition: background-color 0.2s;
  }
  .submit-button:hover {
    background-color: #16a34a;
  }
  .submit-button:disabled {
    background-color: #9ca3af;
    cursor: not-allowed;
  }
  .results-section {
    margin-top: 2rem;
    text-align: left;
    padding: 1.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background-color: #fafafa;
  }
  .spinner {
    width: 40px;
    height: 40px;
    border: 4px solid #f3f3f3;
    border-top: 4px solid #22c55e;
    border-radius: 50%;
    margin: 0 auto 1rem;
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  pre {
    white-space: pre-wrap;
    word-wrap: break-word;
    background: #f8fafc;
    padding: 1.5rem;
    border-radius: 8px;
    font-family: monospace;
    line-height: 1.6;
    border: 1px solid #e2e8f0;
    color: #334155;
  }
  .error {
    color: #dc2626;
    font-weight: bold;
  }
</style>