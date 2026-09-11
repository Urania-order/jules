import numpy as np

class EmbeddingService:
    def get_embedding(self, text: str):
        # Placeholder for real embedding generation
        # Using a deterministic random-ish vector for testing
        np.random.seed(hash(text) % (2**32))
        return np.random.rand(1536).tolist()

embedding_service = EmbeddingService()
