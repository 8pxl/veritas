import cv2
import json
import base64
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
VERIFICATION_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct" # 400B-class reasoning for vision

# Initialize client from environment
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE")
)

def run_groq_verification_pipeline(video_path, transcript_path, interest_factor):
    # 1. Load Transcript
    with open(transcript_path, 'r') as f:
        transcript_data = json.load(f)
    
    # Pre-format the transcript so the LLM understands the structure
    transcript_text = json.dumps(transcript_data[:100]) # Slice if too long for Llama 3.1 8B

    # --- TURN 1: Robust Candidate Selection ---
    print("Step 1: Identifying segments...")
    
    # We define a strict prompt and use JSON mode
    sys_prompt = (
        f"You are a video analyst. Analyze the transcript for: {interest_factor}. "
        "Output a JSON object with a key 'interesting_stamps' containing a list of "
        "float timestamps representing the exact start of the interesting segments."
    )

    turn1_response = client.chat.completions.create(
        model=VERIFICATION_MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Transcript Data: {transcript_text}"}
        ],
        response_format={"type": "json_object"} # Crucial for Llama models on Groq
    )
    
    raw_content = json.loads(turn1_response.choices[0].message.content)
    candidates = raw_content.get("interesting_stamps", [])

    # --- TURN 2: Multimodal Verification ---
    results = []
    cap = cv2.VideoCapture(video_path)

    for ts in candidates:
        # OFFSET: Move 500ms into the segment to ensure the visual has updated
        cap.set(cv2.CAP_PROP_POS_MSEC, (ts * 1000) + 500)
        success, frame = cap.read()
        if not success: continue

        # RESIZE: Groq has limits on base64 size; resizing ensures stability
        frame = cv2.resize(frame, (1280, 720)) 
        _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        base64_image = base64.b64encode(buffer).decode('utf-8')

        print(f"Step 2: Verifying timestamp {ts}s...")
        
        # Explicit prompt for the proposition
        v_prompt = (
            f"Context: The transcript indicated a '{interest_factor}' here. "
            "Look at this frame. Use the frame to add context and create a "
            "short, factual proposition of what is happening. "
            "An example proposition could be : 'Elon is in legal trouble' if"
            "the interest factor was determined based on 'issues'"
            "Another example could be: 'Tesla Roadster will be released in 2026 October'"
            "if the interest factor was determined based on 'product, performance and decisions'"
        )

        turn2_response = client.chat.completions.create(
            model=VERIFICATION_MODEL,
            messages=[
            {
                "role": "system",
                "content": "You are a video analyst. Return a proposition that should be a short statement."
            },
            {
                "role": "user",
                "content": [
                {"type": "text", "text": v_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ],
            }
            ],
            response_format={"type": "text"}
        )
        
        verification = turn2_response.choices[0].message.content
        results.append({
            "timestamp": ts,
            "proposition": verification
        })

    cap.release()
    return results

if __name__ == "__main__":
    video_path = "elon_2.mp4"
    transcript_path = "transcript.json"
    interest_factor = "X is in legal trouble"
    # pivot to using "product, performance and decisions " as the interest factor
    results = run_groq_verification_pipeline(video_path, transcript_path, interest_factor)
    print(json.dumps(results, indent=2))
    # save results to a file
    with open("propositions.json", "w") as f:
        json.dump(results, f, indent=2)