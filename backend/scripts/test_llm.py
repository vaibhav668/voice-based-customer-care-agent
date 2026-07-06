from app.ai.llm.factory import get_llm

llm = get_llm()

print(
    llm.invoke("Say Hello in one sentence.")
)