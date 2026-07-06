from app.ai.rag.embeddings import embeddings

try:
    from langchain_chroma import Chroma
    vectordb = Chroma(
        collection_name="support_ai",
        persist_directory="./chroma_db",
        embedding_function=embeddings,
    )
except Exception as e:
    print("VectorDB Chroma initialization fallback notice:", e)

    class FallbackVectorDB:
        def as_retriever(self, search_kwargs=None):
            class DummyRetriever:
                def invoke(self, question):
                    return []
            return DummyRetriever()

    vectordb = FallbackVectorDB()