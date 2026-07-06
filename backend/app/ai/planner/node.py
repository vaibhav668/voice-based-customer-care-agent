from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.factory import get_llm
from app.ai.planner.prompt import PLANNER_PROMPT
from app.ai.planner.schema import PlannerOutput
from app.ai.utils.json_parser import parse_json

llm = get_llm()


def plan(message: str) -> PlannerOutput:

    messages = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=message),
    ]

    response = llm.invoke(messages)

    if hasattr(response, "content"):
        response = response.content

    data = parse_json(response)

    return PlannerOutput(**data)