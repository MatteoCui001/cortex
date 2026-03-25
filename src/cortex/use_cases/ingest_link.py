"""
Link ingestion: fetch URL content, extract text, store original, ingest.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urlparse

import httpx

from cortex.domain.entities import KnowledgeEvent
from cortex.domain.ports import EmbeddingPort, LLMPort, StoragePort


class IngestLinkUseCase:

    def __init__(
        self,
        storage: StoragePort,
        embedding: EmbeddingPort,
        llm: Optional[LLMPort] = None,
        file_store=None,
        workspace_id: str = "default",
    ):
        self._storage = storage
        self._embedding = embedding
        self._llm = llm
        self._file_store = file_store
        self._workspace_id = workspace_id

    async def import_link(
        self,
        url: str,
        *,
        user_annotation: Optional[str] = None,
    ) -> Optional[KnowledgeEvent]:
        """Fetch a URL, extract text, and ingest as an event."""
        # 1. Fetch content
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Cortex/1.0"})
            resp.raise_for_status()
            html = resp.text

        # 2. Extract text
        text, title = _extract_text(html, url)
        if not text.strip():
            return None

        # 3. Save original to file store
        raw_input_ref = None
        if self._file_store:
            slug = _url_slug(url)
            raw_input_ref = self._file_store.save(
                html.encode("utf-8"),
                "link",
                slug,
                "html",
            )

        # 4. Generate deterministic source_path for dedup
        source_path = f"link:{url}"

        # 5. Ingest via the standard pipeline
        from cortex.use_cases.ingest import IngestUseCase
        ingest = IngestUseCase(
            self._storage, self._embedding, self._llm, self._workspace_id
        )
        event = await ingest.import_text(
            title=title,
            content=text,
            source="web",
            source_path=source_path,
            raw_input_type="link",
            raw_input_ref=raw_input_ref or url,
            user_annotation=user_annotation,
        )
        return event


def _extract_text(html: str, url: str) -> tuple[str, str]:
    """Extract readable text and title from HTML."""
    try:
        import trafilatura
        result = trafilatura.extract(html, include_comments=False, include_tables=True)
        meta = trafilatura.extract_metadata(html)
        title = meta.title if meta and meta.title else _url_slug(url)
        return result or "", title
    except ImportError:
        pass

    # Fallback: basic HTML stripping
    import re
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else _url_slug(url)
    # Strip tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, title


def _url_slug(url: str) -> str:
    """Generate a short slug from URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").split("/")[-1] if parsed.path else parsed.netloc
    if not path or path == "/":
        path = parsed.netloc.replace(".", "-")
    return path[:60]
