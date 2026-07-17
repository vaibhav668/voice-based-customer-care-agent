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

    def invoke(self, query: str, history: list = None) -> list[Document]:
        if not self.knowledge_path.exists():
            return []

        # Use LLM to translate regional queries and expand them to clean English keywords
        search_terms = query
        try:
            from app.ai.llm.factory import get_llm
            from langchain_core.messages import SystemMessage
            llm = get_llm()
            
            history_str = ""
            if history:
                history_str = "\n".join(
                    f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                    for msg in history[-5:]
                )
                
            prompt = f"""
            You are a translation and keyword-expansion assistant for a RAG retrieval system.
            The knowledge base documents are written in English and cover bus policies (baggage, cancellation, refund, rescheduling, payment, faq).
            Your goal is to rewrite the user's message into a concise list of 2-5 English keywords to search these policy documents.
            
            Guidelines:
            - If the message is in Hindi, Telugu, Tamil, Marathi, or other languages, translate the core terms to English.
            - Resolve any pronouns/references using the Conversation History.
            - Output ONLY space-separated English search keywords. Do not explain, greet, or use markdown.
            
            Conversation History:
            {history_str}
            
            User's Message:
            {query}
            
            Search Keywords:
            """
            response = llm.invoke([SystemMessage(content=prompt)])
            rewritten = response.content.strip() if hasattr(response, "content") else str(response).strip()
            if rewritten:
                search_terms = rewritten
        except Exception as e:
            print(f"Notice: RAG query rewrite failed: {e}")

        # Clean query: lowercase and remove special characters
        clean_query = re.sub(r'[^a-zA-Z0-9\s]', '', search_terms.lower())
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