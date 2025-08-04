import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Union, List


class EmbeddingModel:
    """Wrapper class for sentence transformer embedding model."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the embedding model.
        
        Args:
            model_name: Name of the sentence transformer model
        """
        self.model_name = model_name
        self.model = None
    
    def load_model(self) -> None:
        """Load the sentence transformer model."""
        print(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        print("✓ Model loaded successfully!")
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Numpy array containing the embedding
        """
        if self.model is None:
            self.load_model()
        
        # Clean and preprocess text
        text = text.strip()
        if not text:
            # Return zero vector for empty text
            return np.zeros(384)  # all-MiniLM-L6-v2 has 384 dimensions
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding
    
    def get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for multiple texts (more efficient).
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            Numpy array containing all embeddings
        """
        if self.model is None:
            self.load_model()
        
        # Clean texts
        cleaned_texts = [text.strip() if text.strip() else " " for text in texts]
        
        embeddings = self.model.encode(cleaned_texts, convert_to_numpy=True)
        return embeddings


# Global model instance
_embedding_model = EmbeddingModel()


def load_model() -> None:
    """Load the global embedding model."""
    _embedding_model.load_model()


def get_embedding(text: str) -> np.ndarray:
    """
    Get embedding for text using the global model instance.
    
    Args:
        text: Input text to embed
        
    Returns:
        Numpy array containing the embedding
    """
    return _embedding_model.get_embedding(text)


def get_embeddings_batch(texts: List[str]) -> np.ndarray:
    """
    Get embeddings for multiple texts using the global model instance.
    
    Args:
        texts: List of input texts to embed
        
    Returns:
        Numpy array containing all embeddings
    """
    return _embedding_model.get_embeddings_batch(texts)
