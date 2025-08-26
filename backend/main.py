# main.py

import os
import openai
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from vercel_blob import put
import mimetypes # To guess the content type of the files

# --- Configuration ---
# Load environment variables from a .env file for local development
load_dotenv()

# Initialize the FastAPI app
app = FastAPI(title="Kisan Mitra AI Backend")

# --- CORS Middleware ---
# This is crucial for allowing our frontend (running on a different domain)
# to communicate with this backend.
origins = [
    "http://localhost:5173",  # SvelteKit dev server
    "http://localhost:3000",  # Common alternative dev port
    "https://kisan-mitra-2w7six32y-coder7657s-projects.vercel.app", # FIXED: Your new Vercel URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Use the specific list of origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- OpenAI API Client ---
# Set the API key for the OpenAI client
# It's best practice to use environment variables for keys
try:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
except ValueError as e:
    print(f"Error: {e}")
    # You might want to handle this more gracefully in a real app
    # For now, we'll print the error and continue.

# --- API Endpoints ---
@app.get("/")
def read_root():
    """A simple root endpoint to confirm the server is running."""
    return {"message": "Welcome to the Kisan Mitra AI Backend!"}


@app.post("/analyze/")
async def analyze_farm_data(
    image_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
):
    """
    This is the main endpoint that receives farm data, uploads it to blob storage,
    and gets an analysis from OpenAI.
    """
    try:
        # --- 1. Upload files to Vercel Blob Storage ---
        # We need to read the content of the files into memory first
        image_contents = await image_file.read()
        audio_contents = await audio_file.read()

        # Guess the content type of the files
        image_content_type = mimetypes.guess_type(image_file.filename)[0] or 'application/octet-stream'
        audio_content_type = mimetypes.guess_type(audio_file.filename)[0] or 'application/octet-stream'
        
        print(f"Uploading {image_file.filename} with content type {image_content_type}")
        print(f"Uploading {audio_file.filename} with content type {audio_content_type}")

        # Call put() with positional arguments for pathname and body
        image_blob = put(
            f"uploads/{image_file.filename}", 
            image_contents, 
            options={'token': os.getenv("BLOB_READ_WRITE_TOKEN"), 'content_type': image_content_type}
        )
        audio_blob = put(
            f"uploads/{audio_file.filename}", 
            audio_contents, 
            options={'token': os.getenv("BLOB_READ_WRITE_TOKEN"), 'content_type': audio_content_type}
        )

        print(f"Image URL: {image_blob['url']}")
        print(f"Audio URL: {audio_blob['url']}")

        # --- 2. Transcribe Audio using OpenAI Whisper ---
        # OpenAI's API can take the file content directly for transcription
        await audio_file.seek(0) # Reset file pointer after reading
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file.file,
            response_format="text"
        )
        
        print(f"Farmer's Query (from audio): {transcript}")


        # --- 3. Call OpenAI for Analysis ---
        # Construct the prompt for the AI model
        prompt_message = f"""
        You are "Kisan Mitra AI," an expert agricultural diagnostic assistant powered by Gemini 2.5 Pro.
        Analyze the following data from a farmer and provide a hyper-personalized, actionable diagnosis and recommendation.

        **Farmer's Spoken Query (from audio):**
        "{transcript}"

        **Visual Evidence (from image):**
        Please analyze the image available at the following URL: {image_blob['url']}
        In the image, look for visual cues of plant disease, pest infestation, soil condition, water stress, or any other relevant agricultural indicators.

        **Your Task:**
        Based on the two sources of information (audio query and image analysis), provide a response in Markdown format that includes:
        1.  **Diagnosis:** A clear and concise identification of the primary problem(s).
        2.  **Detailed Explanation:** Explain the reasoning behind your diagnosis, referencing specific evidence from the image and audio.
        3.  **Actionable Recommendations:** Provide a step-by-step plan for the farmer to follow. Be specific about treatments, products (suggesting generic types rather than brands), and techniques.
        4.  **Preventative Measures:** Suggest long-term strategies to prevent this issue from recurring.
        """

        # Make the API call
        chat_completion = openai.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt_message,
                }
            ],
            model="gpt-4o", # Using gpt-4o as it's highly capable with multimodal-like text prompts
        )

        analysis_result = chat_completion.choices[0].message.content

        # --- 4. Return the Result ---
        return {
            "analysis": analysis_result,
            "image_url": image_blob['url'],
            "audio_url": audio_blob['url'],
            "transcript": transcript
        }

    except Exception as e:
        # If anything goes wrong, return a detailed error
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
