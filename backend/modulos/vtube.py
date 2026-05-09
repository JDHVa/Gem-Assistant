import asyncio
import json
import numpy as np
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from backend.config import ajustes

EXPRESIONES: dict[str, str] = {
    "alegre": "Joy",
    "estresado": "Angry",
    "confundido": "Sorrow",
    "sorprendido": "Fun",
    "neutro": "Neutral",
}


class VTubeCliente:
    def __init__(self):
        self._uri = f"ws://localhost:{ajustes.vtube_ws_port}"
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._conectado: bool = False
        self._token: str | None = None
        self._expresion_actual: str = "Neutral"

    async def conectar(self) -> bool:
        try:
            self._ws = await websockets.connect(
                self._uri,
                open_timeout=3,
                ping_timeout=5,
            )
            self._conectado = await self._autenticar()
            return self._conectado
        except Exception:
            self._conectado = False
            return False

    async def _enviar(self, payload: dict) -> None:
        if self._ws and self._conectado:
            await self._ws.send(json.dumps(payload))

    async def _recibir(self, timeout: float = 3.0) -> dict | None:
        try:
            data = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            return json.loads(data)
        except Exception:
            return None

    async def _autenticar(self) -> bool:
        try:
            await self._ws.send(
                json.dumps(
                    {
                        "apiName": "VTubeStudioPublicAPI",
                        "apiVersion": "1.0",
                        "requestID": "gem_auth_token",
                        "messageType": "AuthenticationTokenRequest",
                        "data": {
                            "pluginName": "GEM Assistant",
                            "pluginDeveloper": "Jesus",
                            "pluginIcon": None,
                        },
                    }
                )
            )
            resp = await self._recibir()
            if not resp:
                return False
            self._token = resp.get("data", {}).get("authenticationToken")
            if not self._token:
                return False

            await self._ws.send(
                json.dumps(
                    {
                        "apiName": "VTubeStudioPublicAPI",
                        "apiVersion": "1.0",
                        "requestID": "gem_auth",
                        "messageType": "AuthenticationRequest",
                        "data": {
                            "pluginName": "GEM Assistant",
                            "pluginDeveloper": "Jesus",
                            "authenticationToken": self._token,
                        },
                    }
                )
            )
            resp2 = await self._recibir()
            return bool(resp2 and resp2.get("data", {}).get("authenticated", False))
        except Exception:
            return False

    async def set_expresion(self, emocion: str) -> None:
        if not self._conectado:
            return
        expresion_id = EXPRESIONES.get(emocion, "f_neutral")
        if expresion_id == self._expresion_actual:
            return
        try:
            if self._expresion_actual != "f_neutral":
                await self._enviar(
                    {
                        "apiName": "VTubeStudioPublicAPI",
                        "apiVersion": "1.0",
                        "requestID": "gem_expr_off",
                        "messageType": "ExpressionActivationRequest",
                        "data": {
                            "expressionFile": f"{self._expresion_actual}.exp3.json",
                            "active": False,
                        },
                    }
                )
            await self._enviar(
                {
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": "gem_expr_on",
                    "messageType": "ExpressionActivationRequest",
                    "data": {
                        "expressionFile": f"{expresion_id}.exp3.json",
                        "active": True,
                    },
                }
            )
            self._expresion_actual = expresion_id
        except (ConnectionClosed, WebSocketException):
            self._conectado = False

    async def lip_sync_frame(self, amplitud: float) -> None:
        if not self._conectado:
            return
        valor = float(np.clip(amplitud * 4.0, 0.0, 1.0))
        try:
            await self._enviar(
                {
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": "gem_lip",
                    "messageType": "InjectParameterDataRequest",
                    "data": {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "MouthOpen", "value": valor},
                            {"id": "MouthSmile", "value": valor * 0.3},
                        ],
                    },
                }
            )
        except (ConnectionClosed, WebSocketException):
            self._conectado = False

    async def reproducir_con_lipsync(self, mp3_bytes: bytes) -> None:
        if not self._conectado or not mp3_bytes:
            return
        try:
            import miniaudio

            decoded = miniaudio.decode(
                mp3_bytes,
                output_format=miniaudio.SampleFormat.FLOAT32,
            )
            audio = np.array(decoded.samples, dtype=np.float32)
            chunk_size = decoded.sample_rate // 20
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i : i + chunk_size]
                if len(chunk) == 0:
                    break
                amplitud = float(np.sqrt(np.mean(chunk**2)))
                await self.lip_sync_frame(amplitud)
                await asyncio.sleep(0.05)
        except Exception:
            pass

    async def desconectar(self) -> None:
        self._conectado = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
