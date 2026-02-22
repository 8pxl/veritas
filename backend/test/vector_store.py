import chromadb


class VectorStore:
    """Vector DB wrapper to isolate backend-specific operations."""

    def __init__(self, path: str = "./chroma_db"):
        self._client = chromadb.PersistentClient(path=path)

    def _get_collection(self, name: str):
        return self._client.get_or_create_collection(
            name, metadata={"hnsw:space": "cosine"}
        )

    def reset_collections(self, names: list[str]):
        for name in names:
            try:
                self._client.delete_collection(name)
            except Exception:
                pass
            self._get_collection(name)

    def reset_face_audio_collections(self):
        self.reset_collections(["faces", "audio"])

    def add_face_embedding(self, embedding_id: str, embedding: list[float], metadata: dict):
        self._get_collection("faces").add(
            embeddings=[embedding], ids=[embedding_id], metadatas=[metadata]
        )

    def add_audio_embedding(
        self, embedding_id: str, embedding: list[float], metadata: dict
    ):
        self._get_collection("audio").add(
            embeddings=[embedding], ids=[embedding_id], metadatas=[metadata]
        )

    def query_face_embeddings(self, embedding: list[float], n_results: int = 3):
        return self._get_collection("faces").query(
            query_embeddings=[embedding], n_results=n_results
        )

    def query_audio_embeddings(self, embedding: list[float], n_results: int = 3):
        return self._get_collection("audio").query(
            query_embeddings=[embedding], n_results=n_results
        )
