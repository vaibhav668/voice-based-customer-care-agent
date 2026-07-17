from app.ai.rag.retriever import retriever
from app.ai.llm.factory import get_llm

llm = get_llm()


class FAQTool:

    def execute(
        self,
        question,
        history=None,
    ):

        docs = retriever.invoke(question, history=history)

        context = "\n\n".join(
            d.page_content
            for d in docs
        )

        prompt = f"""
Answer only from the following knowledge.

{context}

Question:

{question}
"""

        return llm.invoke(prompt)