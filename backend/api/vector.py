import os
import httpx
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("OPENAI_API_KEY")
print("API Key loaded:", bool(KEY))

response = httpx.post(
    "https://api.openai.com/v1/embeddings",
    headers={
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "text-embedding-3-small",
        "input": "Sundar Pichai CEO Google",
    },
    timeout=30.0,
)
response.raise_for_status()
data = response.json()
print(f"Embedding dimension: {len(data['data'][0]['embedding'])}")
print(f"First 5 values: {data['data'][0]['embedding'][:5]}")