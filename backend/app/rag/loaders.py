"""Document loaders for RAG system."""

from __future__ import annotations

import frontmatter
import markdown
from pathlib import Path
from typing import Any

from backend.app.rag.config import RAGConfig


class DocumentLoadError(Exception):
    """Raised when document loading fails."""


class DocumentLoader:
    """Load and extract text from various document formats."""

    def __init__(self, config: RAGConfig):
        self.config = config

    def load_file(self, file_path: Path) -> dict[str, Any]:
        """Load a single file and extract text with metadata."""
        if not file_path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")

        if file_path.suffix not in self.config.allowed_extensions:
            raise DocumentLoadError(
                f"Unsupported file extension: {file_path.suffix}"
            )

        # Check if file should be excluded
        for excluded in self.config.excluded_files:
            if excluded in file_path.name:
                raise DocumentLoadError(f"File excluded: {file_path.name}")

        text_content = ""
        metadata: dict[str, Any] = {
            "source": str(file_path),
            "file_name": file_path.name,
            "file_type": file_path.suffix,
        }

        try:
            with file_path.open(encoding="utf-8") as f:
                content = f.read()

            # Handle markdown files with frontmatter
            if file_path.suffix == ".md":
                post = frontmatter.loads(content)
                text_content = post.content
                metadata.update(post.metadata)
            else:
                text_content = content

            # Convert markdown to plain text for better chunking
            if file_path.suffix == ".md":
                html = markdown.markdown(text_content)
                # Simple HTML to text conversion
                text_content = (
                    html.replace("<h1>", "\n# ")
                    .replace("</h1>", "\n")
                    .replace("<h2>", "\n## ")
                    .replace("</h2>", "\n")
                    .replace("<h3>", "\n### ")
                    .replace("</h3>", "\n")
                    .replace("<p>", "")
                    .replace("</p>", "\n")
                    .replace("<li>", "- ")
                    .replace("</li>", "\n")
                    .replace("<ul>", "")
                    .replace("</ul>", "")
                    .replace("<ol>", "")
                    .replace("</ol>", "")
                    .replace("<code>", "`")
                    .replace("</code>", "`")
                    .replace("<strong>", "**")
                    .replace("</strong>", "**")
                    .replace("<em>", "*")
                    .replace("</em>", "*")
                )

            if not text_content.strip():
                raise DocumentLoadError(f"Empty content in file: {file_path}")

            return {"content": text_content, "metadata": metadata}

        except UnicodeDecodeError:
            raise DocumentLoadError(f"Encoding error in file: {file_path}")
        except Exception as e:
            raise DocumentLoadError(f"Error loading file {file_path}: {e}") from e

    def load_directory(self, directory: Path) -> list[dict[str, Any]]:
        """Load all supported documents from a directory."""
        documents = []

        if not directory.exists():
            raise DocumentLoadError(f"Directory not found: {directory}")

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix in self.config.allowed_extensions:
                try:
                    doc = self.load_file(file_path)
                    documents.append(doc)
                except DocumentLoadError:
                    # Skip files that can't be loaded
                    continue

        return documents
