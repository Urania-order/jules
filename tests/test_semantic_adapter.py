import pytest
from smos.services.embedding_fallback import HashFallbackAdapter


def test_fallback_adapter_dimension():
    adapter = HashFallbackAdapter(dimension=512, model_name="test-hash-512")
    assert adapter.dimension == 512
    assert adapter.model_name == "test-hash-512"

    vec = adapter.embed("hello world")
    assert len(vec) == 512


def test_fallback_adapter_deterministic():
    adapter = HashFallbackAdapter(dimension=128)
    vec1 = adapter.embed("test query string")
    vec2 = adapter.embed("test query string")
    assert vec1 == vec2


def test_same_text_same_vector():
    adapter = HashFallbackAdapter(dimension=256)
    v1 = adapter.embed("Phenomenon: Urban Heat Island")
    v2 = adapter.embed("Phenomenon: Urban Heat Island")
    assert v1 == v2


def test_different_texts_produce_vectors():
    adapter = HashFallbackAdapter(dimension=256)
    v1 = adapter.embed("Text A")
    v2 = adapter.embed("Text B")
    assert len(v1) == 256
    assert len(v2) == 256
    # While vectors could mathematically overlap, HashFallbackAdapter produces distinct PRNG sequences for distinct seeds
    assert v1 != v2


def test_embed_batch():
    adapter = HashFallbackAdapter(dimension=64)
    texts = ["a", "b", "c"]
    vecs = adapter.embed_batch(texts)
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == 64
