# embedding_utils.py
from sentence_transformers import SentenceTransformer
import logging
from typing import List, Optional

class EmbeddingGenerator:
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingGenerator, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        if self._model is None:
            try:
                self._model = SentenceTransformer(model_name)
                logging.info(f"Loaded embedding model: {model_name}")
            except Exception as e:
                logging.error(f"Failed to load embedding model: {e}")
                self._model = None
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        
        if self._model is None:
            return None
            
        try:
            embedding = self._model.encode([text], convert_to_numpy=True)[0]
            return embedding.tolist()
        except Exception as e:
            logging.error(f"Failed to generate embedding: {e}")
            return None

embedding_generator = EmbeddingGenerator()

def generate_embedding(text: str) -> Optional[List[float]]:
    return embedding_generator.generate_embedding(text)
