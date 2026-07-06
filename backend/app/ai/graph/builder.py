from langgraph.graph import END, START, StateGraph

from app.ai.graph.nodes import chat_node
from app.ai.state.graph_state import GraphState


def build_graph():

    graph = StateGraph(GraphState)

    graph.add_node(
        "chat",
        chat_node,
    )

    graph.add_edge(
        START,
        "chat",
    )

    graph.add_edge(
        "chat",
        END,
    )

    return graph.compile()