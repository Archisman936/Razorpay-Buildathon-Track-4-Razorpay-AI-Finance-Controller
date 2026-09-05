"""Script to ingest documents into the RAG vector store."""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Also add parent directory to allow backend imports
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))

from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging, get_logger
from backend.app.rag import get_rag_service

configure_logging()
logger = get_logger(__name__)


def main():
    """Main ingestion function."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest documents into RAG vector store")
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Clear existing vector store before ingestion",
    )
    parser.add_argument(
        "--docs-path",
        type=str,
        help="Override default documents path",
    )

    args = parser.parse_args()

    try:
        settings = get_settings()

        # Override docs path if provided
        if args.docs_path:
            settings.rag_documents_path = Path(args.docs_path)
            logger.info("Using custom documents path: %s", settings.rag_documents_path)

        # Get RAG service
        rag_service = get_rag_service(settings)

        logger.info("Starting RAG document ingestion...")
        logger.info("Documents path: %s", settings.rag_documents_path)
        logger.info("Vector DB path: %s", settings.rag_vector_db_path)
        logger.info("Force rebuild: %s", args.force_rebuild)

        # Run ingestion
        result = rag_service.ingest_documents(force_rebuild=args.force_rebuild)

        logger.info("Ingestion completed: %s", result)
        print("\n" + "=" * 50)
        print("RAG INGESTION COMPLETE")
        print("=" * 50)
        print(f"Status: {result['status']}")
        print(f"Documents loaded: {result['documents_loaded']}")
        print(f"Chunks created: {result['chunks_created']}")
        print(f"Vector store count: {result.get('vector_store_count', 'N/A')}")
        print(f"Message: {result['message']}")
        print("=" * 50)

        return 0

    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        print(f"\nERROR: Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
