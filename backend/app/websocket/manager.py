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

    async def broadcast(self, message: str):
        active_connections = list(self.connections)
        for connection in active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                try:
                    self.connections.remove(connection)
                except Exception:
                    pass

    def broadcast_sync(self, message: str):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast(message))
        except Exception:
            pass