from unittest.mock import MagicMock, patch
import pytest
from smos.services.embedding_service import EmbeddingService, embedding_service


def test_get_embedding_dims(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = EmbeddingService()
    vec = service.get_embedding("hello world")
    assert isinstance(vec, list)
    assert len(vec) == 1536
    assert all(isinstance(x, float) for x in vec)


def test_get_embedding_deterministic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = EmbeddingService()
    text = "Co-SMOS quantum memory node"
    vec1 = service.get_embedding(text)
    vec2 = service.get_embedding(text)
    assert vec1 == vec2


def test_different_texts_different_vectors(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = EmbeddingService()
    vec1 = service.get_embedding("text A")
    vec2 = service.get_embedding("text B")
    assert vec1 != vec2


def test_get_embeddings_batch(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = EmbeddingService()
    texts = ["one", "two", "three", "four"]
    batch_vecs = service.get_embeddings_batch(texts)
    assert len(batch_vecs) == len(texts)
    for vec in batch_vecs:
        assert len(vec) == 1536
    assert batch_vecs[0] == service.get_embedding("one")
    assert batch_vecs[1] == service.get_embedding("two")


def test_fallback_without_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = EmbeddingService()
    vec = service.get_embedding("fallback test")
    assert len(vec) == 1536


def test_openai_api_key_mock(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key-123")
    service = EmbeddingService()

    fake_embedding = [0.1] * 1536
    mock_data = MagicMock()
    mock_data.embedding = fake_embedding
    mock_response = MagicMock()
    mock_response.data = [mock_data]

    with patch("smos.services.embedding_service.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = mock_response

        vec = service.get_embedding("openai test")
        assert vec == fake_embedding
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="openai test"
        )


def test_openai_batch_mock(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key-123")
    service = EmbeddingService()

    fake_embedding_1 = [0.1] * 1536
    fake_embedding_2 = [0.2] * 1536

    mock_item1 = MagicMock()
    mock_item1.index = 0
    mock_item1.embedding = fake_embedding_1

    mock_item2 = MagicMock()
    mock_item2.index = 1
    mock_item2.embedding = fake_embedding_2

    mock_response = MagicMock()
    mock_response.data = [mock_item1, mock_item2]

    with patch("smos.services.embedding_service.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = mock_response

        batch = service.get_embeddings_batch(["text1", "text2"])
        assert len(batch) == 2
        assert batch[0] == fake_embedding_1
        assert batch[1] == fake_embedding_2
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["text1", "text2"]
        )


def test_edge_cases_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = EmbeddingService()

    # Empty string
    vec_empty = service.get_embedding("")
    assert len(vec_empty) == 1536

    # None input
    vec_none = service.get_embedding(None)
    assert vec_none == vec_empty

    # Unicode characters
    vec_unicode = service.get_embedding("Реалізація EmbeddingService 🚀")
    assert len(vec_unicode) == 1536

    # Empty batch
    assert service.get_embeddings_batch([]) == []
