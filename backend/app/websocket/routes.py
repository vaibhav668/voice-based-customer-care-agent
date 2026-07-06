from fastapi import APIRouter, WebSocket

from app.ai.llm.factory import get_llm
from app.websocket.manager import ConnectionManager
from langchain_core.messages import HumanMessage
router = APIRouter()

manager = ConnectionManager()

llm = get_llm()


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
):

    await manager.connect(websocket)

    try:

        while True:

            message = await websocket.receive_text()

            for token in llm.stream(
                [
                    HumanMessage(
                        content=message
                    )
                ]
            ):

                await manager.send(
                    websocket,
                    token,
                )

    finally:

        manager.disconnect(websocket)