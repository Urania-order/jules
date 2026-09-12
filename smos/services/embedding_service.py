import os
import hashlib
from typing import List
import numpy as np

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class EmbeddingService:
    """Service for generating vector embeddings for text inputs.

    Supports OpenAI embeddings (`text-embedding-3-small`) when `OPENAI_API_KEY` is configured,
    and falls back to a deterministic hash-seeded pseudo-random vector generation when no key is present.
    """

    def __init__(self, model: str = "text-embedding-3-small", dimensions: int = 1536):
        self.model = model
        self.dimensions = dimensions

    def _get_fallback_embedding(self, text: str) -> List[float]:
        """Generates a deterministic vector of length `self.dimensions` based on the text hash.

        Edge cases handled:
        - Non-string inputs: converted to str.
        - Empty/whitespace strings: UTF-8 encoded consistently.
        - Unicode text: encoded using UTF-8 before computing hash.
        - Python's built-in `hash()` is process-dependent due to SIPHASH seed randomization across runs.
          Therefore `hashlib.sha256` is used to ensure identical vectors across Python restarts/processes.
        """
        if text is None:
            text = ""
        else:
            text = str(text)

        # Hash text deterministically across process restarts using SHA-256
        text_bytes = text.encode("utf-8")
        hash_digest = hashlib.sha256(text_bytes).digest()
        
        # Take first 4 bytes as 32-bit unsigned integer seed
        seed = int.from_bytes(hash_digest[:4], byteorder="big")

        # Create isolated RandomState generator so global numpy seed is not altered
        rng = np.random.RandomState(seed)
        return rng.rand(self.dimensions).tolist()

    def get_embedding(self, text: str) -> List[float]:
        """Returns 1536-dimensional embedding vector for the given text.

        Uses OpenAI API if `OPENAI_API_KEY` is present in environment,
        otherwise uses deterministic fallback generation.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and OpenAI is not None:
            try:
                client = OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    model=self.model,
                    input=text,
                )
                return response.data[0].embedding
            except Exception:
                # Fall back gracefully if API call fails
                return self._get_fallback_embedding(text)

        return self._get_fallback_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Returns a list of 1536-dimensional embedding vectors for a list of texts.

        Batch requests are sent to OpenAI API when `OPENAI_API_KEY` is set, or
        processed sequentially using fallback generator otherwise.
        """
        if not texts:
            return []

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and OpenAI is not None:
            try:
                client = OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                # Ensure ordered output matching input list
                sorted_data = sorted(response.data, key=lambda x: x.index)
                return [item.embedding for item in sorted_data]
            except Exception:
                # Fall back gracefully if API batch call fails
                return [self._get_fallback_embedding(t) for t in texts]

        return [self._get_fallback_embedding(t) for t in texts]


embedding_service = EmbeddingService()
