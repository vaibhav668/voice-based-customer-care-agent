from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        self.connections = []

    async def connect(
        self,
        websocket: WebSocket,
    ):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(
        self,
        websocket: WebSocket,
    ):
        self.connections.remove(websocket)

    async def send(
        self,
        websocket: WebSocket,
        message: str,
    ):
        await websocket.send_text(message)