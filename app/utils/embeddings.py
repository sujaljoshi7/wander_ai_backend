# app/utils/embeddings.py
from sentence_transformers import SentenceTransformer

# load model once at startup
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text: str) -> list[float]:
    if not text:
        return []
    return embedder.encode(text).tolist()
