import os
import logging
import re
from pathlib import Path
from langchain_core.documents import Document
from app.ai.rag.embeddings import embeddings

logger = logging.getLogger("app.company_support.vectorstore")

# Resolve knowledge_base folder relative to backend root
BACKEND_DIR = Path(__file__).parent.parent.parent.resolve()
KNOWLEDGE_BASE_DIR = BACKEND_DIR / "knowledge_base"

# Persist directory for company support chroma
CHROMA_PERSIST_DIR = str(BACKEND_DIR / "chroma_db_company")
COLLECTION_NAME = "company_support_kb"

class FallbackCompanyRetriever:
    """Fallback keyword retriever that scans knowledge_base documents in memory."""
    def __init__(self, kb_dir: Path):
        self.kb_dir = kb_dir
        self._cache = {}
        self.reload()

    def reload(self):
        self._cache.clear()
        if not self.kb_dir.exists():
            return
        logger.info("Initializing Fallback Company Knowledge Base Cache...")
        
        # Walk recursively through all files in knowledge_base
        for file_path in self.kb_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in [".md", ".txt"]:
                try:
                    # Determine category (subfolder name)
                    category = file_path.parent.name
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._cache[str(file_path.relative_to(self.kb_dir))] = {
                        "content": content,
                        "category": category,
                        "name": file_path.name
                    }
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")

    def invoke(self, query: str) -> list[Document]:
        clean_query = re.sub(r'[^\w\s]', ' ', query.lower())
        query_words = set(clean_query.split())
        
        # Stopwords filter
        stopwords = {
            "tell", "me", "the", "policy", "what", "is", "how", "much", "do",
            "you", "have", "about", "rules", "for", "please", "show", "can",
            "ask", "question", "get", "info", "information"
        }
        keywords = query_words - stopwords
        if not keywords:
            keywords = query_words

        scored_docs = []
        for rel_path, data in self._cache.items():
            content_lower = data["content"].lower()
            score = 0
            
            # Boost matches in the filename or directory category
            if any(kw in data["name"].lower() for kw in keywords):
                score += 15
            if any(kw in data["category"].lower() for kw in keywords):
                score += 10
                
            # Count keyword occurrences in content
            for kw in keywords:
                score += content_lower.count(kw)

            if score > 0:
                scored_docs.append((
                    score,
                    Document(
                        page_content=data["content"],
                        metadata={
                            "source": rel_path,
                            "category": data["category"]
                        }
                    )
                ))

        # Sort by score descending and return top 4 documents
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:4]]


# Global vector store or fallback retriever
company_vectordb = None
fallback_retriever = None

try:
    from langchain_chroma import Chroma
    company_vectordb = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=embeddings,
    )
    logger.info("Chroma initialized successfully for Company Support.")
except Exception as e:
    logger.warning(f"Chroma initialization fallback notice for Company Support: {e}")
    fallback_retriever = FallbackCompanyRetriever(KNOWLEDGE_BASE_DIR)


def get_company_retriever():
    """Returns either the Chroma retriever or the Fallback retriever."""
    global company_vectordb, fallback_retriever
    if company_vectordb is not None:
        try:
            return company_vectordb.as_retriever(search_kwargs={"k": 4})
        except Exception as e:
            logger.error(f"Failed to get Chroma retriever: {e}. Switching to fallback.")
            if fallback_retriever is None:
                fallback_retriever = FallbackCompanyRetriever(KNOWLEDGE_BASE_DIR)
            return fallback_retriever
    else:
        if fallback_retriever is None:
            fallback_retriever = FallbackCompanyRetriever(KNOWLEDGE_BASE_DIR)
        return fallback_retriever


def ingest_company_knowledge(force: bool = False) -> dict:
    """Ingests files from the knowledge_base folder into the Chroma vectorstore (if available)."""
    global company_vectordb, fallback_retriever
    
    if not KNOWLEDGE_BASE_DIR.exists():
        return {"status": "error", "message": f"Knowledge base directory does not exist: {KNOWLEDGE_BASE_DIR}"}

    documents = []
    supported_extensions = [".md", ".txt"]
    
    # Try parsing pdf/docx if dependencies exist
    has_pdf_parser = False
    try:
        from pypdf import PdfReader
        has_pdf_parser = True
    except ImportError:
        pass

    for file_path in KNOWLEDGE_BASE_DIR.rglob("*"):
        if not file_path.is_file():
            continue
            
        suffix = file_path.suffix.lower()
        rel_path = str(file_path.relative_to(KNOWLEDGE_BASE_DIR))
        category = file_path.parent.name
        
        if suffix in supported_extensions:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                if text.strip():
                    documents.append(Document(
                        page_content=text,
                        metadata={"source": rel_path, "category": category}
                    ))
            except Exception as e:
                logger.warning(f"Failed to read file {rel_path}: {e}")
                
        elif suffix == ".pdf" and has_pdf_parser:
            try:
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if text.strip():
                    documents.append(Document(
                        page_content=text,
                        metadata={"source": rel_path, "category": category}
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse PDF {rel_path}: {e}")

    if not documents:
        return {"status": "warning", "message": "No documents found to index."}

    # Split documents into chunks
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=120)
    except ImportError:
        class SimpleSplitter:
            def split_documents(self, docs):
                chunks = []
                for d in docs:
                    text = d.page_content
                    start = 0
                    while start < len(text):
                        chunks.append(Document(
                            page_content=text[start:start+600],
                            metadata=d.metadata
                        ))
                        start += 480
                return chunks
        splitter = SimpleSplitter()

    chunks = splitter.split_documents(documents)

    if company_vectordb is not None:
        try:
            # Recreate/clear Chroma collection if force is True
            if force:
                try:
                    company_vectordb.delete_collection()
                except Exception:
                    pass
                company_vectordb = Chroma(
                    collection_name=COLLECTION_NAME,
                    persist_directory=CHROMA_PERSIST_DIR,
                    embedding_function=embeddings,
                )
            
            company_vectordb.add_documents(chunks)
            logger.info(f"Indexed {len(chunks)} chunks into Chroma.")
            return {"status": "success", "message": f"Successfully indexed {len(chunks)} chunks into Chroma vector store."}
        except Exception as e:
            logger.error(f"Failed to index in Chroma: {e}. Reloading fallback.")
            if fallback_retriever is None:
                fallback_retriever = FallbackCompanyRetriever(KNOWLEDGE_BASE_DIR)
            fallback_retriever.reload()
            return {"status": "fallback_success", "message": f"Chroma error: {e}. Indexed {len(documents)} files in memory fallback."}
    else:
        if fallback_retriever is None:
            fallback_retriever = FallbackCompanyRetriever(KNOWLEDGE_BASE_DIR)
        fallback_retriever.reload()
        return {"status": "fallback_success", "message": f"Indexed {len(documents)} files in memory fallback."}
