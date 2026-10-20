# main.py

import base64
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
        You are "Kisan Mitra AI", an agricultural assistant. A farmer has sent a photo of their crop
        (attached) and a spoken question.

        **Farmer's spoken question (transcribed):**
        "{transcript}"

        **Rules:**
        - Describe only what you can actually see in the attached photo. If the photo is unclear, or
          doesn't show the problem, say so plainly instead of guessing.
        - Do not give pesticide, fungicide or fertiliser doses, and do not name brands. Say which kind
          of treatment may help, and tell the farmer to confirm the product and dose with their local
          Krishi Vigyan Kendra (KVK) or agriculture officer before using any chemical.
        - If you are not confident in a diagnosis, say that, and recommend showing the crop to the KVK.
        - Reply in the same language the farmer used, in simple words.

        **Reply in Markdown with:**
        1. **What I can see:** what the photo shows, and how sure you are.
        2. **Likely problem:** the most likely cause, and other possibilities.
        3. **What to do now:** practical steps, without doses or brands.
        4. **Prevention:** what helps stop it coming back.
        """

        # Send the photo itself as an image part. A URL written into the text is never opened by the
        # model, which is how earlier replies came to describe photos it had not seen.
        image_data_url = f"data:{image_content_type};base64,{base64.b64encode(image_contents).decode('ascii')}"
        chat_completion = openai.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_message},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            model="gpt-4o",
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
