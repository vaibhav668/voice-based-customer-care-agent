from langchain_core.messages import HumanMessage

from app.ai.llm.factory import get_llm

llm = get_llm()

for token in llm.stream(
    [
        HumanMessage(
            content="Explain AI in one paragraph."
        )
    ]
):
    print(token, end="", flush=True)