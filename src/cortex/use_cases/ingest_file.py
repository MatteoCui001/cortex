"""
File ingestion: extract text from PDF/DOCX/TXT, store original, ingest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from cortex.domain.entities import KnowledgeEvent
from cortex.domain.ports import EmbeddingPort, LLMPort, StoragePort


class IngestFileUseCase:

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

    async def import_file(
        self,
        file_path: str,
        *,
        user_annotation: Optional[str] = None,
    ) -> Optional[KnowledgeEvent]:
        """Extract text from a file and ingest as an event."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        text = _extract_text(path, ext)
        if not text.strip():
            return None

        title = path.stem.replace("-", " ").replace("_", " ")

        # Save original to file store
        raw_input_ref = None
        if self._file_store:
            category = _ext_to_category(ext)
            raw_input_ref = self._file_store.save(
                path.read_bytes(),
                category,
                title,
                ext.lstrip("."),
            )

        source_path = f"file:{path.name}"

        from cortex.use_cases.ingest import IngestUseCase
        ingest = IngestUseCase(
            self._storage, self._embedding, self._llm, self._workspace_id
        )
        event = await ingest.import_text(
            title=title,
            content=text,
            source="file",
            source_path=source_path,
            raw_input_type="file",
            raw_input_ref=raw_input_ref or str(path),
            user_annotation=user_annotation,
        )
        return event


def _extract_text(path: Path, ext: str) -> str:
    """Extract text from various file formats."""
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf(path)

    if ext in (".docx", ".doc"):
        return _extract_docx(path)

    if ext == ".md":
        return path.read_text(encoding="utf-8", errors="replace")

    # Fallback: try reading as text
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using pymupdf or pdfplumber."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n\n".join(pages)
    except ImportError:
        pass

    raise ImportError("PDF extraction requires pymupdf or pdfplumber. Install: pip install pymupdf")


def _extract_docx(path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        raise ImportError("DOCX extraction requires python-docx. Install: pip install python-docx")


def _ext_to_category(ext: str) -> str:
    """Map file extension to file store category."""
    mapping = {
        ".pdf": "documents",
        ".docx": "documents",
        ".doc": "documents",
        ".txt": "documents",
        ".md": "articles",
        ".png": "images",
        ".jpg": "images",
        ".jpeg": "images",
        ".mp3": "recordings",
        ".wav": "recordings",
        ".m4a": "recordings",
        ".mp4": "videos",
        ".mov": "videos",
    }
    return mapping.get(ext, "documents")
