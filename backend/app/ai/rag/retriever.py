import re
import logging
from pathlib import Path
from langchain_core.documents import Document

logger = logging.getLogger("app.rag")

class KeywordBasedRetriever:
    """A lightweight, zero-dependency keyword retriever to prevent
    PyTorch/Chroma memory issues on Render Free Tier."""

    def __init__(self):
        # Resolve backend root path
        self.backend_dir = Path(__file__).parent.parent.parent.parent.resolve()
        self.knowledge_path = self.backend_dir / "knowledge"
        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        """Loads all knowledge base documents into memory once at startup."""
        if not self.knowledge_path.exists():
            return
        logger.info("Initializing RAG Knowledge Base Cache...")
        for file in self.knowledge_path.glob("*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    self._cache[file.name] = f.read()
            except Exception as e:
                logger.warning(f"Failed to cache knowledge file {file.name}: {e}")

    def invoke(self, query: str, history: list = None, search_keywords: str = None) -> list[Document]:
        # If search_keywords are pre-extracted by the understanding engine, use them directly
        # to achieve 0ms additional latency. Otherwise fall back to local keyword parsing.
        search_terms = search_keywords or query

        # Keep all Unicode word characters (including Devanagari/Hindi, Telugu, Tamil, etc.)
        clean_query = re.sub(r'[^\w\s]', ' ', search_terms.lower())
        query_words = set(clean_query.split())

        # Domain synonyms mapping Hindi & common STT variations to knowledge files
        SYNONYMS = {
            "baggage": ["baggage", "luggage", "सामान", "नगेज", "नगेर", "बैग", "सामान की नीति", "सामान नीत"],
            "refund": ["refund", "रिफंड", "रिपुंड", "पैसा वापस", "वापस", "रिफर्न"],
            "cancellation": ["cancel", "cancellation", "रद्द", "निरस्त", "कैंसिल", "अवरिफ्रेंड"],
            "rescheduling": ["reschedule", "rescheduling", "बदल", "तारीख बदल"],
            "payment": ["payment", "भुगतान", "पेमेंट", "पैसा"],
        }

        # Expand query keywords with matching file synonyms
        expanded_keywords = set(query_words)
        for doc_key, syn_list in SYNONYMS.items():
            if any(syn in search_terms.lower() for syn in syn_list):
                expanded_keywords.add(doc_key)

        stopwords = {
            "tell", "me", "the", "policy", "what", "is", "how", "much", "do",
            "you", "have", "about", "rules", "for", "please", "show", "can",
            "ask", "question", "जाननी", "है", "की", "मुझे", "क्या", "बताएं"
        }
        keywords = expanded_keywords - stopwords
        if not keywords:
            keywords = expanded_keywords

        scored_docs = []
        # Score documents from memory cache
        for filename, content in self._cache.items():
            clean_content = content.lower()
            score = 0
            for kw in keywords:
                if kw in filename.lower():
                    score += 10
                score += clean_content.count(kw)

            if score > 0:
                scored_docs.append((
                    score,
                    Document(
                        page_content=content,
                        metadata={"source": filename}
                    )
                ))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:3]]


retriever = KeywordBasedRetriever()