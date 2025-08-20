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

// Helper to transcribe audio using Whisper
async function transcribeAudioFromUrl(audioUrl, openaiClient) {
    // Note: The OpenAI Node.js library currently requires a file stream, not a URL.
    // The simplest way to handle this is to fetch the audio and pass it.
    const audioResponse = await fetch(audioUrl);
    if (!audioResponse.ok) {
        throw new Error(`Failed to fetch audio file: ${audioResponse.statusText}`);
    }
    const transcription = await openaiClient.audio.transcriptions.create({
        model: "whisper-1",
        file: audioResponse, // The fetch response can be directly passed
    });
    return transcription.text;
}

// ---------------------------
// Main API Endpoint
// ---------------------------
export async function POST({ request }) {
    try {
        // 1. Get the URLs from the frontend request body
        // For this to work, the frontend will now send a base64 image string instead of a video URL.
        // This simplifies the logic immensely.
        const { base64Image, audioUrl, farmHistoryUrl } = await request.json();

        if (!base64Image || !audioUrl || !farmHistoryUrl) {
            return json({ error: 'Missing required data.' }, { status: 400 });
        }

        // 2. Securely get the OpenAI API Key and initialize the client
        const openAIKey = env.OPENAI_API_KEY;
        if (!openAIKey) {
            return json({ error: 'OpenAI API key is not configured on the server.' }, { status: 500 });
        }
        const openai = new OpenAI({ apiKey: openAIKey });

        // 3. Fetch text and transcribe audio in parallel for speed
        const [farm_history_text, user_question] = await Promise.all([
            getTextFromUrl(farmHistoryUrl),
            transcribeAudioFromUrl(audioUrl, openai)
        ]);
        
        // 4. Call OpenAI with the multimodal payload
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
                                "url": `data:image/jpeg;base64,${base64Image}`
                            },
                        },
                    ],
                }
            ],
            max_tokens: 600,
        });
        
        const aiResponseText = response.choices[0].message.content;

        // 5. Send the AI's response back to the frontend
        return json({ result: aiResponseText }, { status: 200 });

    } catch (error) {
        console.error('Error in analysis endpoint:', error);
        return json({ error: 'An unexpected error occurred during analysis.' }, { status: 500 });
    }
}