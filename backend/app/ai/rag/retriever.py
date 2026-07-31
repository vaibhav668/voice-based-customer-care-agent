import re
import logging
from pathlib import Path
from langchain_core.documents import Document

logger = logging.getLogger("app.rag")

class KeywordBasedRetriever:
    """A lightweight, zero-dependency keyword chunk retriever to prevent
    PyTorch/Chroma memory issues on Render Free Tier."""

    def __init__(self):
        # Resolve backend root path
        self.backend_dir = Path(__file__).parent.parent.parent.parent.resolve()
        self.knowledge_path = self.backend_dir / "knowledge"
        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        """Loads and splits all knowledge base documents into memory once at startup."""
        if not self.knowledge_path.exists():
            return
        logger.info("Initializing RAG Paragraph-Level Knowledge Base Cache...")
        for file in self.knowledge_path.glob("*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Split content into paragraphs/sections by double newlines
                paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                
                # Group section headers with their corresponding text paragraphs
                current_header = ""
                file_chunks = []
                for p in paragraphs:
                    if p.startswith("#"):
                        current_header = p
                    else:
                        chunk_text = f"{current_header}\n{p}" if current_header else p
                        file_chunks.append(chunk_text)
                
                # Fallback: if no chunks were extracted, use the raw content as a single chunk
                if not file_chunks and content.strip():
                    file_chunks = [content.strip()]
                    
                self._cache[file.name] = file_chunks
            except Exception as e:
                logger.warning(f"Failed to cache knowledge file {file.name}: {e}")

    def invoke(self, query: str, history: list = None, search_keywords: str = None) -> list[Document]:
        # If search_keywords are pre-extracted by the understanding engine, use them directly
        # to achieve 0ms additional latency. Otherwise fall back to local keyword parsing.
        search_terms = search_keywords or query

        # Keep all Unicode word characters (including Devanagari/Hindi, Telugu, Tamil, etc.)
        clean_query = re.sub(r'[^\w\s]', ' ', search_terms.lower())
        query_words = set(clean_query.split())

        # Expanded domain synonyms mapping English, Hindi, and Telugu variations to file keys
        SYNONYMS = {
            "baggage": [
                "baggage", "luggage", "standard luggage", "oversized", "allowance", "carry", "weight", "limit",
                "सामान", "नगेज", "नगेर", "बैग", "लगेज", "वेट", "लिमिट",
                "సామాను", "సామాన్లు", "లగేజ్", "సంచులు", "బరువు"
            ],
            "refund": [
                "refund", "refunding", "refunded", "reimburse", "timeline", "money back",
                "रिफंड", "रिपुंड", "पैसा वापस", "वापस", "पैसे",
                "రీఫండ్", "రిఫండ్", "డబ్బులు", "తిరిగి", "వాపస్"
            ],
            "cancellation": [
                "cancel", "cancellation", "cancelling", "void", "abort",
                "रद्द", "कैंसिल", "निरस्त", "कैन्सलेशन",
                "రద్దు", "క్యాన్సిల్", "క్యాన్సల్", "రద్దుచేయడం"
            ],
            "rescheduling": [
                "reschedule", "rescheduling", "postpone", "prepone", "change date", "modify date",
                "बदल", "तारीख बदल", "चेंज", "रीशेड्यूल",
                "రీషెడ్యూల్", "మార్చడం", "తేదీ మార్పు", "సమయం మార్పు"
            ],
            "payment": [
                "payment", "pay", "charge", "charged", "fee", "cost", "price", "deducted", "transaction",
                "भुगतान", "पेमेंट", "पैसे", "पे", "कट",
                "పేమెంట్", "చెల్లింపు", "ధర", "ఫీజు"
            ],
            "faq": [
                "policy", "rules", "wifi", "pets", "dog", "cat", "animal", "carrier", "lost", "medicine", "liability",
                "वाइफाई", "पालतू", "कुत्ता", "बिल्ली", "पालिसी", "दवाई", "खोया",
                "పాలసీ", "నిబంధనలు", "వైఫై", "జంతువులు", "పెట్స్", "కుక్క", "పిల్లి", "మందులు", "పోగొట్టు"
            ]
        }

        # Expand query keywords with matching synonyms
        expanded_keywords = set(query_words)
        for doc_key, syn_list in SYNONYMS.items():
            if any(syn in search_terms.lower() for syn in syn_list):
                expanded_keywords.add(doc_key)

        stopwords = {
            "tell", "me", "the", "policy", "what", "is", "how", "much", "do",
            "you", "have", "about", "rules", "for", "please", "show", "can",
            "ask", "question", "जाननी", "है", "की", "मुझे", "क्या", "बताएं",
            "చెప్పండి", "ఉంది", "పాలసీ", "ఏమిటి", "ఎంత", "సరే"
        }
        keywords = expanded_keywords - stopwords
        if not keywords:
            keywords = expanded_keywords

        scored_chunks = []
        # Score each cached paragraph/chunk individually
        for filename, chunks in self._cache.items():
            for chunk in chunks:
                clean_chunk = chunk.lower()
                score = 0
                for kw in keywords:
                    # Boost score if keyword matches source filename
                    if kw in filename.lower():
                        score += 15
                    # Term frequency with BM25-like saturation (cap counts at 5)
                    count = min(clean_chunk.count(kw), 5)
                    score += count * 2
                    
                    # Boost header matching
                    first_line = clean_chunk.split("\n")[0] if "\n" in clean_chunk else clean_chunk
                    if kw in first_line:
                        score += 10

                if score > 0:
                    scored_chunks.append((
                        score,
                        Document(
                            page_content=chunk,
                            metadata={"source": filename}
                        )
                    ))

        # Sort by score descending and return the top 2 most relevant chunks
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_chunks[:2]]


retriever = KeywordBasedRetriever()