"""
Broadcaster para WebSockets.
Permite enviar mensajes a todos los clientes conectados.
"""

from fastapi import WebSocket
import asyncio
import logging

log = logging.getLogger("gem.broadcaster")


class Broadcaster:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)
        log.info("Cliente WebSocket conectado (%d activos)", len(self._connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)
            log.info(
                "Cliente WebSocket desconectado (%d activos)", len(self._connections)
            )

    async def broadcast(self, message: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


broadcaster = Broadcaster()
