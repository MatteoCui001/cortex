"""
Link ingestion: fetch URL content, extract text, store original, ingest.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx


class SSRFError(ValueError):
    """Raised when a URL targets a private/reserved network address."""


def _validate_url_safe(url: str) -> None:
    """Block URLs that resolve to private, loopback, or link-local addresses."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError(f"Invalid URL: no hostname in {url!r}")

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SSRFError(f"Blocked scheme: {scheme!r}")

    # Resolve hostname to IP(s) and check each
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise SSRFError(
                f"Blocked: {hostname} resolves to private/reserved address {ip}"
            )

from cortex.domain.entities import KnowledgeEvent
from cortex.domain.ports import EmbeddingPort, LLMPort, StoragePort

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _is_wechat_article(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ("mp.weixin.qq.com",)


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
        _validate_url_safe(url)

        is_wechat = _is_wechat_article(url)

        # 1. Fetch content — WeChat needs browser-like headers
        headers = {
            "User-Agent": _BROWSER_UA if is_wechat else "Cortex/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        # 2. Extract text — specialised path for WeChat articles
        if is_wechat:
            text, title = _extract_wechat_article(html, url)
        else:
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


def _extract_wechat_article(html: str, url: str) -> tuple[str, str]:
    """Extract article body and title from a WeChat Official Account page.

    WeChat articles are server-rendered. The body lives in ``#js_content``
    and metadata (title, author, timestamp) is in ``<script>`` variable
    assignments.  Rate-limited pages lack ``#js_content`` entirely.
    """
    # --- Title from script var or <title> ---
    title = ""
    m = re.search(r'var\s+msg_title\s*=\s*["\'](.+?)["\']', html)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        title = m.group(1).strip() if m else _url_slug(url)

    # --- Author from meta or script ---
    author = ""
    m = re.search(r'<meta\s+name=["\']author["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if m:
        author = m.group(1).strip()
    if not author:
        m = re.search(r'var\s+nickname\s*=\s*["\'](.+?)["\']', html)
        if m:
            author = m.group(1).strip()

    # --- Body from #js_content ---
    body_html = ""
    m = re.search(
        r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>\s*(?=<div|<script|$)',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        body_html = m.group(1)

    if not body_html:
        # Rate-limited or non-standard page — fall back to trafilatura
        return _extract_text(html, url)

    # Strip HTML tags to plain text
    text = re.sub(r"<br\s*/?>", "\n", body_html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if author:
        title = f"{title} — {author}"

    return text, title


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
