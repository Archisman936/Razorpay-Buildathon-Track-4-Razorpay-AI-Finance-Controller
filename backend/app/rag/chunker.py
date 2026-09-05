"""Document chunking for RAG system."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List
from uuid import uuid4

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    chunk_id: str
    content: str
    metadata: dict[str, Any]
    chunk_index: int


class DocumentChunker:
    """Split documents into semantic chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, document: dict[str, Any]) -> List[Chunk]:
        """Split a document into chunks while preserving structure."""
        content = document["content"]
        metadata = document["metadata"].copy()

        # First, try to split by headers to preserve sections
        chunks = self._split_by_structure(content, metadata)

        # If structure splitting didn't work well, fall back to size-based
        if not chunks or all(len(c.content) < 100 for c in chunks):
            chunks = self._split_by_size(content, metadata)

        # Add chunk IDs and indices
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = f"{metadata.get('file_name', 'doc')}_{uuid4().hex[:8]}_{i}"
            chunk.chunk_index = i

        return chunks

    def _split_by_structure(self, content: str, metadata: dict[str, Any]) -> List[Chunk]:
        """Split content by markdown headers and list items."""
        chunks = []

        # Split by headers
        sections = re.split(r"\n(#{1,3}\s.+?)\n", content)

        current_section = ""
        current_metadata = metadata.copy()

        for i, part in enumerate(sections):
            if i % 2 == 1:  # This is a header
                if current_section.strip():
                    chunks.append(
                        Chunk(
                            chunk_id="",
                            content=current_section.strip(),
                            metadata=current_metadata.copy(),
                            chunk_index=0,
                        )
                    )
                current_section = part + "\n"
                current_metadata = metadata.copy()
                current_metadata["section"] = part.strip()
            else:  # This is content
                current_section += part

        # Add the last section
        if current_section.strip():
            chunks.append(
                Chunk(
                    chunk_id="",
                    content=current_section.strip(),
                    metadata=current_metadata.copy(),
                    chunk_index=0,
                )
            )

        # Further split large sections by size
        final_chunks = []
        for chunk in chunks:
            if len(chunk.content) > self.chunk_size:
                sub_chunks = self._split_text_by_size(chunk.content, self.chunk_size, self.chunk_overlap)
                for j, sub_content in enumerate(sub_chunks):
                    sub_metadata = chunk.metadata.copy()
                    sub_metadata["sub_chunk"] = j
                    final_chunks.append(
                        Chunk(
                            chunk_id="",
                            content=sub_content,
                            metadata=sub_metadata,
                            chunk_index=j,
                        )
                    )
            else:
                final_chunks.append(chunk)

        return final_chunks

    def _split_by_size(self, content: str, metadata: dict[str, Any]) -> List[Chunk]:
        """Split content purely by size with overlap."""
        chunks = []
        text_chunks = self._split_text_by_size(content, self.chunk_size, self.chunk_overlap)

        for i, chunk_content in enumerate(text_chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunks.append(
                Chunk(
                    chunk_id="",
                    content=chunk_content,
                    metadata=chunk_metadata,
                    chunk_index=i,
                )
            )

        return chunks

    def _split_text_by_size(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into chunks of specified size with overlap."""
        chunks = []
        start = 0
        max_chunks = 1000  # Safety limit to prevent memory issues
        chunk_count = 0

        while start < len(text) and chunk_count < max_chunks:
            end = start + chunk_size

            # Try to break at a sentence boundary near the end
            if end < len(text):
                search_start = start + max(1, chunk_size // 2)
                best_end = -1
                for delimiter in [". ", "! ", "? ", "\n\n", "\n"]:
                    last_delim = text.rfind(delimiter, search_start, end)
                    if last_delim != -1:
                        candidate_end = last_delim + len(delimiter)
                        if candidate_end > best_end:
                            best_end = candidate_end
                if best_end != -1:
                    end = best_end

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                chunk_count += 1

            # Advance start ensuring strictly forward progress
            next_start = end - overlap
            if next_start <= start:
                next_start = start + max(1, chunk_size - overlap)
            start = next_start

        if chunk_count >= max_chunks:
            logger.warning("Document too large, limited to %d chunks", max_chunks)

        return chunks
