import re
from pathlib import Path
from langchain_core.documents import Document


class KeywordBasedRetriever:
    """A lightweight, zero-dependency keyword retriever to prevent
    PyTorch/Chroma memory issues on Render Free Tier."""

    def __init__(self):
        # Resolve backend root path
        self.backend_dir = Path(__file__).parent.parent.parent.parent.resolve()
        self.knowledge_path = self.backend_dir / "knowledge"

    def invoke(self, query: str) -> list[Document]:
        if not self.knowledge_path.exists():
            return []

        # Clean query: lowercase and remove special characters
        clean_query = re.sub(r'[^a-zA-Z0-9\s]', '', query.lower())
        query_words = set(clean_query.split())

        # Simple stop words to filter out noise
        stopwords = {
            "tell", "me", "the", "policy", "what", "is", "how", "much", "do",
            "you", "have", "about", "rules", "for", "please", "show", "can",
            "ask", "question"
        }
        keywords = query_words - stopwords
        if not keywords:
            keywords = query_words  # fallback if all words are stopwords

        scored_docs = []
        for file in self.knowledge_path.glob("*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Clean content for scoring
                clean_content = content.lower()

                # Calculate simple score: count of matching keywords
                score = 0
                for kw in keywords:
                    # Give higher weight to matches in filenames
                    if kw in file.name.lower():
                        score += 5
                    # Count occurrences in content
                    score += clean_content.count(kw)

                if score > 0:
                    scored_docs.append((
                        score,
                        Document(
                            page_content=content,
                            metadata={"source": file.name}
                        )
                    ))
            except Exception:
                pass

        # Sort by score descending and return the Documents
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:3]]


retriever = KeywordBasedRetriever()