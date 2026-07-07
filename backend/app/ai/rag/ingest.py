import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.rag.vectordb import vectordb

logger = logging.getLogger(__name__)


def ingest_knowledge_base(force: bool = False):
    try:
        # Check if collection has documents (if vectordb has get method)
        existing_ids = []
        if hasattr(vectordb, "get"):
            existing = vectordb.get()
            existing_ids = existing.get("ids", []) if existing else []

        if len(existing_ids) > 0 and not force:
            logger.info("RAG Knowledge base already populated. Skipping ingestion.")
            return

        # Resolve path relative to backend root
        backend_dir = Path(__file__).parent.parent.parent.parent.resolve()
        knowledge_path = backend_dir / "knowledge"

        if not knowledge_path.exists():
            logger.warning(f"Knowledge path {knowledge_path} does not exist.")
            return

        documents = []
        for file in knowledge_path.glob("*.md"):
            with open(file, "r", encoding="utf-8") as f:
                documents.append(
                    Document(
                        page_content=f.read(),
                        metadata={"source": file.name},
                    )
                )

        if not documents:
            logger.warning("No knowledge documents found to ingest.")
            return

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
        )
        chunks = splitter.split_documents(documents)

        # Clear existing if force is True and has docs
        if force and len(existing_ids) > 0 and hasattr(vectordb, "delete"):
            vectordb.delete(ids=existing_ids)

        if hasattr(vectordb, "add_documents"):
            vectordb.add_documents(chunks)
            logger.info(f"Successfully indexed {len(chunks)} RAG chunks.")
        else:
            logger.warning("vectordb does not support add_documents. Skipping.")
    except Exception as e:
        logger.warning(f"RAG Ingestion warning: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_knowledge_base(force=True)