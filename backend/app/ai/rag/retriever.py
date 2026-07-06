from app.ai.rag.vectordb import vectordb

retriever = vectordb.as_retriever(
    search_kwargs={
        "k": 4
    }
)