from langchain_core.messages import HumanMessage

from app.ai.graph.builder import build_graph

graph = build_graph()

state = {
    "messages": [
        HumanMessage(
             content="My bus is delayed"
        )
    ]
}

result = graph.invoke(state)

print(result["response"])