import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Point the OpenAI library to Groq's servers
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE")
)

def transcribe_with_groq(file_path):
    with open(file_path, "rb") as audio_file:
        # Note: You MUST use a Groq-supported model name here
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo", 
            file=audio_file,
            response_format="verbose_json",  # Mandatory for timestamps
            timestamp_granularities=["segment"] # Optional but helpful
        )
    return transcription.segments

print(transcribe_with_groq("temp_audio.mp3"))