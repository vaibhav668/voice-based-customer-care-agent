from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.rag.vectordb import vectordb

knowledge_path = Path("knowledge")

documents = []

for file in knowledge_path.glob("*.md"):
    with open(file, "r", encoding="utf-8") as f:
        documents.append(
            Document(
                page_content=f.read(),
                metadata={"source": file.name},
            )
        )

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
)

chunks = splitter.split_documents(documents)

vectordb.add_documents(chunks)

print(f"Indexed {len(chunks)} chunks successfully.")