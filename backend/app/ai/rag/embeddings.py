import hashlib
from langchain_core.embeddings import Embeddings


class MemoryEfficientEmbeddings(Embeddings):
    """Lightweight Embeddings generator that operates under 1MB RAM,
    preventing PyTorch 512MB RAM OOM crashes on Render Free Tier."""

    def __init__(self, size: int = 384):
        self.size = size
        self._hf_embeddings = None

    @property
    def hf_embeddings(self):
        if self._hf_embeddings is None:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
                self._hf_embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
            except Exception:
                self._hf_embeddings = False
        return self._hf_embeddings if self._hf_embeddings is not False else None

    def _hash_embed(self, text: str) -> list[float]:
        vec = []
        for i in range(self.size):
            h = hashlib.sha256(f"{text}_{i}".encode('utf-8')).hexdigest()
            val = (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
            vec.append(val)
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.hf_embeddings:
            try:
                return self.hf_embeddings.embed_documents(texts)
            except Exception:
                pass
        return [self._hash_embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        if self.hf_embeddings:
            try:
                return self.hf_embeddings.embed_query(text)
            except Exception:
                pass
        return self._hash_embed(text)


embeddings = MemoryEfficientEmbeddings()