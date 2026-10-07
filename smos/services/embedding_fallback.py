import hashlib
from typing import List
import numpy as np
from smos.services.semantic_adapter import SemanticAdapter


class HashFallbackAdapter(SemanticAdapter):
    """Deterministic hash-based fallback adapter for tests and local development.

    Generates reproducible pseudo-random normalized vectors based on SHA-256 string hash.
    NOT a real semantic embedding model. MUST NOT be used to evaluate semantic quality.
    """

    def __init__(self, dimension: int = 1536, model_name: str = "hash-fallback-v1"):
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, text: str) -> List[float]:
        if text is None:
            text = ""
        else:
            text = str(text)

        text_bytes = text.encode("utf-8")
        hash_digest = hashlib.sha256(text_bytes).digest()
        seed = int.from_bytes(hash_digest[:4], byteorder="big")

        rng = np.random.RandomState(seed)
        vec = rng.rand(self._dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
