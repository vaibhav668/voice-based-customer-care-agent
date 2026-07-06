from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class GraphState(TypedDict):

    messages: Annotated[list, add_messages]

    user_id: str 

    session_id: str

    intent: str

    entities: dict

    response: str