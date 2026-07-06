from langchain_chroma import Chroma

from app.ai.rag.embeddings import embeddings

vectordb = Chroma(
    collection_name="support_ai",
    persist_directory="./chroma_db",
    embedding_function=embeddings,
)