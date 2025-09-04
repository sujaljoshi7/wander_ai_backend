import json
import faiss
from pathlib import Path
from sentence_transformers import SentenceTransformer

DATA_FILE = Path("../../Data/places.json")

# 1. Load model (CPU)
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# 2. Load dataset
if DATA_FILE.exists():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = []

# 3. Convert to plain docs
documents = []
for place in data:
    text = (
        f"{place['name']} in {place['city']}, {place['state']}. "
        f"Type: {place['type']}. {place['description']} "
        f"Best months: {', '.join(place.get('best_months', []))}. "
        f"Entry fee: {place.get('entry_fee', {})}. "
        f"Famous for: {', '.join(place.get('famous_for', []))}."
    )
    documents.append(text)

# 4. Build embeddings
if documents:
    embeddings = embedder.encode(documents, convert_to_numpy=True, show_progress_bar=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    id_map = {i: doc for i, doc in enumerate(documents)}
else:
    index = None
    id_map = {}

def search_places(query: str, top_k: int = 5):
    """Search relevant places from FAISS index"""
    if not index:
        return []
    q_vec = embedder.encode([query], convert_to_numpy=True)
    D, I = index.search(q_vec, top_k)
    return [id_map[i] for i in I[0]]
