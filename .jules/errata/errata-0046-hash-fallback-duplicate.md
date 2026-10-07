# ERRATA-0046: SHA-256 fallback embedding duplicated

## Severity
LOW — duplication, not a bug; TASK 28 aligned with spec

## Symptom
Two independent SHA-256 based fallback embedders exist:
1. smos/services/embedding_service.py _get_fallback_embedding()
2. smos/services/embedding_fallback.py HashFallbackAdapter.embed()

## Comparison
Both use:
- if text is None: text = ""
- text_bytes = text.encode("utf-8")
- hash_digest = hashlib.sha256(text_bytes).digest()
- seed = int.from_bytes(hash_digest[:4], byteorder="big")
- rng = np.random.RandomState(seed)
- vec = rng.rand(dimension)

Difference:
- HashFallbackAdapter applies L2 normalization (vec / np.linalg.norm(vec))
- EmbeddingService does NOT normalize

## Why OK for TASK 28
- TASK 28 explicitly asked for independent SemanticAdapter
- EmbeddingService is production (MemoryNode.embeddings)
- HashFallbackAdapter is test/dev (semantic lay- Has Different responsibilities, different domain
- No broken behavior — both fallbacks work independently

## Risk
- Third semantic task could add a third fallback
- No single source of truth for hash-fallback logic
- Future divergence (e.g., different hash iteration) could cause subtle bugs

## Fix (future TASK, not now)
1. Extract shared helper: smos/services/_hash_fallback.py
   def hash_fallback_vector(text: str, dimension: int, normalize: bool = False) -> List[float]
2. EmbeddingService._get_fallback_embedding -> reuse helper (normalize=False)
3. HashFallbackAdapter.embed -> reuse helper (normalize=True)
4. Tests verify both paths produce identical output for normalize=False

## Related
- TASK 28 (task-20261007-133107)

## Status
OPEN — deferred (not blocking TASK 29)
