import os
import httpx
from dotenv import load_dotenv

load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def person_to_text(name: str, position: str | None, org_name: str) -> str:
    """Build a text representation of a person for embedding."""
    parts = [name]
    if position:
        parts.append(position)
    parts.append(org_name)
    return " ".join(parts)


async def get_embedding(text: str) -> list[float]:
    """Call OpenAI embeddings API and return the embedding vector."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENAI_EMBEDDINGS_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
