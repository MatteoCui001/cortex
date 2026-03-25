"""
File Store adapter: human-readable storage of original input files.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Optional

from cortex.domain.ports import FileStorePort

# Map raw_input_type to store subdirectory
_TYPE_DIR = {
    "link": "articles",
    "text": "articles",
    "audio": "recordings",
    "image": "images",
    "video": "videos",
    "file": "documents",
}


class FileStore(FileStorePort):
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser()
        self._ensure_dirs()

    def _ensure_dirs(self):
        for subdir in ("articles", "documents", "recordings", "images", "videos"):
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

    def save(
        self,
        content: bytes,
        input_type: str,
        subject: str,
        ext: str,
        target_date: Optional[str] = None,
    ) -> str:
        """Save content and return the relative path from store root."""
        subdir = _TYPE_DIR.get(input_type, "documents")
        d = target_date or date.today().strftime("%Y%m%d")
        safe_name = _sanitize(subject)
        filename = f"{safe_name}-{d}.{ext.lstrip('.')}"
        dest = self.root / subdir / filename

        # Avoid overwriting: append counter
        counter = 1
        while dest.exists():
            filename = f"{safe_name}-{d}-{counter}.{ext.lstrip('.')}"
            dest = self.root / subdir / filename
            counter += 1

        dest.write_bytes(content)
        return f"{subdir}/{filename}"

    def exists(self, rel_path: str) -> bool:
        return (self.root / rel_path).exists()

    def read(self, rel_path: str) -> bytes:
        return (self.root / rel_path).read_bytes()

    def absolute(self, rel_path: str) -> Path:
        return self.root / rel_path


def _sanitize(text: str, max_len: int = 60) -> str:
    """Make text filesystem-safe."""
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    # Keep alphanumeric, Chinese chars, hyphens, spaces
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    # Collapse whitespace to hyphens
    text = re.sub(r"\s+", "-", text.strip())
    # Truncate
    return text[:max_len].rstrip("-")
