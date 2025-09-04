from sentence_transformers import SentenceTransformer

# Load model once
embedder = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim

def get_embedding(text: str) -> list[float]:
    return embedder.encode(text).tolist()
