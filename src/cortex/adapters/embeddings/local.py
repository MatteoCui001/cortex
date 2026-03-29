"""Local embedding adapter using sentence-transformers.
Falls back to n-gram hash if sentence-transformers is not installed."""
from __future__ import annotations

import asyncio
import hashlib
import struct
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from cortex.domain.ports import EmbeddingPort

_model = None
_executor = ThreadPoolExecutor(max_workers=2)


class LocalEmbedding(EmbeddingPort):
    """Local embedding using sentence-transformers (or n-gram fallback)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dims: int = 384):
        self._model_name = model_name
        self._dims = dims
        self._st_model = None
        self._use_fallback = False
        self._load_model()

    def _load_model(self):
        try:
            import os, sys, io, warnings, logging

            # Suppress HF Hub noise
            os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            warnings.filterwarnings("ignore")
            logging.disable(logging.WARNING)

            # Redirect stdout/stderr to capture MLX LOAD REPORT noise
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            try:
                from sentence_transformers import SentenceTransformer
                self._st_model = SentenceTransformer(self._model_name)
                self._dims = self._st_model.get_sentence_embedding_dimension()
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                logging.disable(logging.NOTSET)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "sentence-transformers not installed — using n-gram hash fallback. "
                "Semantic search quality will be severely degraded. "
                "Install with: pip install sentence-transformers"
            )
            self._use_fallback = True

    async def embed(self, text: str) -> list[float]:
        if self._use_fallback:
            return _ngram_hash(text, self._dims)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor, lambda: self._st_model.encode(text, normalize_embeddings=True),
        )
        return result.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._use_fallback:
            return [_ngram_hash(t, self._dims) for t in texts]
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _executor, lambda: self._st_model.encode(texts, normalize_embeddings=True, batch_size=32),
        )
        return [r.tolist() for r in results]

    @property
    def dimensions(self) -> int:
        return self._dims


def _ngram_hash(text: str, dims: int, n: int = 3) -> list[float]:
    """Deterministic n-gram hash fallback. Not real semantic embeddings."""
    vec = [0.0] * dims
    text = text.lower().strip()
    for i in range(max(1, len(text) - n + 1)):
        gram = text[i:i + n]
        h = hashlib.md5(gram.encode()).digest()
        idx = struct.unpack("<H", h[:2])[0] % dims
        val = struct.unpack("<f", h[4:8])[0]
        vec[idx] += val
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec
