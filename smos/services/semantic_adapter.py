from abc import ABC, abstractmethod
from typing import List


class SemanticAdapter(ABC):
    """Abstract interface for semantic vector embedding adapters."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns vector output dimensionality."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns name/identifier of the embedding model."""
        ...

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Embeds a single string into a vector representation."""
        ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of strings into vector representations."""
        return [self.embed(text) for text in texts]
