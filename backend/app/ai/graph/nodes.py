from app.ai.llm.factory import get_llm
from app.ai.state.graph_state import GraphState
from app.ai.prompts.system import SYSTEM_PROMPT
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from app.ai.prompts.system import SYSTEM_PROMPT
llm = get_llm()


def chat_node(state: GraphState):

    user_message = state["messages"][-1].content

    messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)

    return {
        "response": response,
    }