// In frontend/src/routes/api/analyze/+server.js
import { json } from '@sveltejs/kit';
import { env } from '$env/dynamic/private'; // Securely access server-side environment variables
import OpenAI from 'openai';

// ---------------------------
// Helper Functions
// ---------------------------

// Helper to fetch text content from a URL
async function getTextFromUrl(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch farm history: ${response.statusText}`);
    }
    return await response.text();
}

// Helper to extract image from video URL (first frame) and convert to base64
async function extractImageFromVideo(videoUrl) {
    try {
        // Fetch the video file as a buffer
        const videoResponse = await fetch(videoUrl);
        if (!videoResponse.ok) {
            throw new Error(`Failed to fetch video file: ${videoResponse.statusText}`);
        }
        
        // For now, we'll return an error asking user to upload image instead of video
        // A full video frame extraction would require ffmpeg or similar
        throw new Error('Video processing not implemented. Please upload a single image of the plant instead of a video.');
    } catch (error) {
        console.error('Video processing error:', error);
        throw error;
    }
}

// Helper to transcribe audio using Whisper (fixed to properly handle file upload)
async function transcribeAudioFromUrl(audioUrl, openaiClient) {
    try {
        // Fetch the audio file and convert it to a proper File object
        const audioResponse = await fetch(audioUrl);
        if (!audioResponse.ok) {
            throw new Error(`Failed to fetch audio file: ${audioResponse.statusText}`);
        }
        
        // Get the audio as an ArrayBuffer
        const audioBuffer = await audioResponse.arrayBuffer();
        
        // Create a File object from the buffer (required by OpenAI API)
        const audioFile = new File([audioBuffer], 'audio.mp3', {
            type: audioResponse.headers.get('content-type') || 'audio/mpeg'
        });
        
        const transcription = await openaiClient.audio.transcriptions.create({
            model: "whisper-1",
            file: audioFile,
        });
        
        return transcription.text;
    } catch (error) {
        console.error('Audio transcription error:', error);
        throw new Error(`Audio transcription failed: ${error.message}`);
    }
}

// ---------------------------
// Main API Endpoint
// ---------------------------

export async function POST({ request }) {
    try {
        // 1. Get the data from the frontend request body
        const requestData = await request.json();
        const { videoUrl, base64Image, audioUrl, farmHistoryUrl } = requestData;
        
        // Check if we have required data
        if (!audioUrl || !farmHistoryUrl) {
            return json({ error: 'Missing required data: audioUrl and farmHistoryUrl are required.' }, { status: 400 });
        }
        
        // We need either a video URL or a base64 image
        if (!videoUrl && !base64Image) {
            return json({ error: 'Missing required data: either videoUrl or base64Image must be provided.' }, { status: 400 });
        }
        
        // 2. Securely get the OpenAI API Key and initialize the client
        const openAIKey = env.OPENAI_API_KEY;
        if (!openAIKey) {
            console.error('Environment variable OPENAI_API_KEY is not set');
            return json({ 
                error: 'OpenAI API key is not configured on the server. Please set the OPENAI_API_KEY environment variable.' 
            }, { status: 500 });
        }
        
        const openai = new OpenAI({ apiKey: openAIKey });
        
        // 3. Process the image - either extract from video or use provided base64
        let imageBase64;
        if (base64Image) {
            // Use the provided base64 image directly
            imageBase64 = base64Image;
        } else if (videoUrl) {
            // Extract image from video (this will currently throw an error asking for image instead)
            imageBase64 = await extractImageFromVideo(videoUrl);
        }
        
        // 4. Fetch text and transcribe audio in parallel for speed
        const [farm_history_text, user_question] = await Promise.all([
            getTextFromUrl(farmHistoryUrl),
            transcribeAudioFromUrl(audioUrl, openai)
        ]);
        
        // 5. Call OpenAI with the multimodal payload
        const response = await openai.chat.completions.create({
            model: "gpt-4o",
            messages: [
                {
                    role: "user",
                    content: [
                        {
                            type: "text",
                            text: `
                                आप 'किसान मित्र AI' हैं - भारतीय किसानों के लिए कृषि वैज्ञानिक विशेषज्ञ।
                                विश्लेषण करें:
                                - किसान का सवाल (ऑडियो से): "${user_question}"
                                - खेत का इतिहास: "${farm_history_text}"
                                - पौधे की छवि (संलग्न)
                                
                                कार्य:
                                1. छवि देखकर पौधे की बीमारी/कीट पहचानें।
                                2. खेत के इतिहास से जोड़कर विश्लेषण दें।
                                3. किसान के प्रश्न का सीधा उत्तर दें।
                                4. स्पष्ट "निदान" शीर्षक लिखें।
                                5. 3 सरल, कम लागत/जैविक उपाय बुलेट लिस्ट में दें।
                                6. पूरा उत्तर आसान हिंदी में लिखें।
                            `
                        },
                        {
                            type: "image_url",
                            image_url: {
                                "url": `data:image/jpeg;base64,${imageBase64}`
                            },
                        },
                    ],
                }
            ],
            max_tokens: 600,
        });
        
        const aiResponseText = response.choices[0].message.content;
        
        // 6. Send the AI's response back to the frontend
        return json({ result: aiResponseText }, { status: 200 });
        
    } catch (error) {
        console.error('Error in analysis endpoint:', error);
        
        // Return more specific error messages
        let errorMessage = 'An unexpected error occurred during analysis.';
        if (error.message.includes('Video processing not implemented')) {
            errorMessage = error.message;
        } else if (error.message.includes('Audio transcription failed')) {
            errorMessage = error.message;
        } else if (error.message.includes('OPENAI_API_KEY')) {
            errorMessage = 'OpenAI API configuration error.';
        }
        
        return json({ error: errorMessage }, { status: 500 });
    }
}
