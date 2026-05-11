import asyncio
import re
import logging
import numpy as np
from backend.modulos.gemini_cliente import generar_respuesta
from backend.modulos.audio import ModuloAudio
from backend.modulos.memoria import MemoriaRAG
from backend.modulos.powershell import clasificar_riesgo, ejecutar, auto_healing
from backend.modulos.vision import ModuloVision
from backend.modulos.broadcaster import Broadcaster
from backend.prompts.system_prompt import construir as construir_prompt

log = logging.getLogger("gem.orquestador")
PATRON_CMD = re.compile(r"^\[CMD:(.+?)\](.*)", re.DOTALL | re.IGNORECASE)

# ── Sistema de emociones ──────────────────────────────────────────────
# Emoción de inicio (cuando GEM arranca)
EMOCION_INICIO    = "alegre"

# Mapa: emoción detectada en cámara → emoción del avatar de GEM
# GEM empatiza con el usuario, pero no se enoja (usa confundido/ansioso en su lugar)
MAPA_ESPEJO = {
    "alegre":    "alegre",
    "neutro":    "neutro",
    "triste":    "triste",
    "enojado":   "confundido",   # GEM no se enoja, muestra empatía/confusión
    "ansioso":   "ansioso",
    "confundido":"confundido",
    "dormido":   "dormido",
    "pensativo": "pensativo",
}

# Emoción de GEM según lo que está haciendo
EMOCION_PROCESANDO = "pensativo"   # Transcribiendo / pensando respuesta
EMOCION_HABLANDO   = "hablando"    # Reproduciendo TTS
EMOCION_ERROR      = "confundido"  # Algo falló
# ─────────────────────────────────────────────────────────────────────


class Orquestador:
    def __init__(self, broadcaster: Broadcaster):
        self._broadcaster  = broadcaster
        self._loop: asyncio.AbstractEventLoop | None = None
        self._historial: list[dict] = []
        self._memoria      = MemoriaRAG()
        self._vision       = ModuloVision()
        self._audio: ModuloAudio | None = None
        self._procesando   = False
        self._silenciado   = False
        self._emocion_gem  = EMOCION_INICIO
        self._tarea_idle: asyncio.Task | None = None

    async def iniciar(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._audio = ModuloAudio(callback_voz=self._on_voz, loop=self._loop)
        self._audio.on_tts_amplitud = self._enviar_lipsync
        self._audio.on_estado_vad   = self._enviar_estado_vad

        try: self._vision.iniciar()
        except Exception as e: log.warning("Visión no disponible: %s", e)

        try: self._audio.iniciar()
        except Exception as e: log.error("Audio no disponible: %s", e)

        # Emitir emoción inicial
        await self._set_emocion(EMOCION_INICIO)

        # Tarea de fondo: actualiza emoción según cámara cuando GEM está idle
        self._tarea_idle = asyncio.create_task(self._loop_espejo_emocion())

    async def detener(self) -> None:
        if self._tarea_idle: self._tarea_idle.cancel()
        if self._audio: self._audio.detener()
        self._vision.detener()

    # ── Gestión de emociones ─────────────────────────────────────────

    async def _set_emocion(self, emocion: str):
        if emocion == self._emocion_gem:
            return
        self._emocion_gem = emocion
        await self._broadcaster.broadcast({"tipo": "expresion", "emocion": emocion})

    async def _set_emocion_idle(self):
        """Cuando GEM termina una tarea, espeja la emoción del usuario o vuelve a alegre."""
        emocion_usuario = self._vision.get_estado().get("emocion", "neutro")
        emocion_gem = MAPA_ESPEJO.get(emocion_usuario, "alegre")
        await self._set_emocion(emocion_gem)

    async def _loop_espejo_emocion(self):
        """Tarea de fondo: actualiza la emoción de GEM según la cámara cada 4s cuando está idle."""
        while True:
            await asyncio.sleep(4)
            if not self._procesando and self._emocion_gem not in (EMOCION_HABLANDO, EMOCION_PROCESANDO):
                await self._set_emocion_idle()

    # ── Broadcasts de estado ─────────────────────────────────────────

    async def _enviar_lipsync(self, rms: float, terminado: bool):
        await self._broadcaster.broadcast(
            {"tipo": "lipsync", "amplitud": rms, "terminado": terminado}
        )

    async def _enviar_estado_vad(self, hablando: bool):
        await self._broadcaster.broadcast({"tipo": "vad", "hablando": hablando})

    async def _enviar_procesando(self, activo: bool):
        await self._broadcaster.broadcast({"tipo": "procesando", "activo": activo})

    # ── Callback del VAD ─────────────────────────────────────────────

    async def _on_voz(self, audio_np: np.ndarray) -> None:
        if self._procesando or self._silenciado or self._audio is None:
            return
        self._procesando = True
        await self._set_emocion(EMOCION_PROCESANDO)   # GEM piensa
        await self._enviar_procesando(True)
        try:
            texto = await self._audio.transcribir(audio_np)
            if texto.strip():
                await self._pipeline(texto.strip())
        except Exception as e:
            log.exception("Error en pipeline: %s", e)
            await self._set_emocion(EMOCION_ERROR)
        finally:
            self._procesando = False
            await self._enviar_procesando(False)
            if self._emocion_gem not in (EMOCION_HABLANDO,):
                await self._set_emocion_idle()

    # ── Pipeline ─────────────────────────────────────────────────────

    def _construir_prompt(self, fragmentos: list[str]) -> str:
        estado = self._vision.get_estado()
        return construir_prompt(
            emocion=estado.get("emocion", "neutro"),
            es_usuario=estado.get("es_usuario", False),
            turnos=len(self._historial) // 2,
            memoria=self._memoria.estadisticas(),
            silenciado=self._silenciado,
            fragmentos_rag=fragmentos,
        )

    async def _pipeline(self, texto_usuario: str) -> str:
        estado = self._vision.get_estado()
        if estado.get("identidad_activa") and not estado.get("es_usuario"):
            await self._responder("No reconozco quién está frente a la cámara.")
            return ""

        fragmentos = await self._memoria.buscar_todo(texto_usuario)
        prompt     = self._construir_prompt(fragmentos)

        self._historial.append({"rol": "user", "texto": texto_usuario})
        if len(self._historial) > 24:
            self._historial = self._historial[-24:]

        # GEM sigue en modo pensativo mientras genera respuesta
        await self._set_emocion(EMOCION_PROCESANDO)

        try:
            respuesta_raw = await generar_respuesta(self._historial, system_prompt=prompt)
        except Exception as e:
            log.exception("Error generando respuesta: %s", e)
            await self._responder("Tuve un problema al generar la respuesta.")
            await self._set_emocion(EMOCION_ERROR)
            return ""

        match = PATRON_CMD.match(respuesta_raw.strip())
        if match:
            comando         = match.group(1).strip()
            texto_respuesta = match.group(2).strip() or "Ejecutando..."
            await self._flujo_comando(comando, texto_usuario)
        else:
            texto_respuesta = respuesta_raw

        self._historial.append({"rol": "model", "texto": texto_respuesta})

        await asyncio.gather(
            self._guardar_conversacion(texto_usuario, texto_respuesta),
            self._responder(texto_respuesta),
            return_exceptions=True,
        )
        return texto_respuesta

    async def _flujo_comando(self, comando: str, instruccion: str) -> None:
        riesgo = await clasificar_riesgo(comando)
        if riesgo == "alto":
            await self._responder(f"Comando de alto riesgo. ¿Confirmas: {comando}? Di sí o no.")
            if self._audio:
                audio = await self._loop.run_in_executor(None, self._audio.grabar_hasta_silencio)
                confirmacion = await self._audio.transcribir(audio)
                if "sí" not in confirmacion.lower() and "si" not in confirmacion.lower():
                    await self._responder("Comando cancelado.")
                    return
        resultado = await ejecutar(comando)
        if resultado["exito"]:
            await self._memoria.guardar_comando_exitoso(instruccion, comando)
        else:
            resultado_fix = await auto_healing(comando, resultado["stderr"])
            if resultado_fix["exito"]:
                await self._memoria.guardar_comando_exitoso(instruccion, resultado_fix["comando_final"])

    async def _responder(self, texto: str) -> None:
        if not self._audio or not texto.strip():
            return
        await self._set_emocion(EMOCION_HABLANDO)    # GEM habla → frames de hablando
        try:
            await self._audio.sintetizar_y_reproducir(texto)
        except Exception as e:
            log.exception("Error reproduciendo: %s", e)
        finally:
            await self._set_emocion_idle()            # Terminó → espeja usuario

    async def _guardar_conversacion(self, pregunta: str, respuesta: str) -> None:
        try:
            await self._memoria.guardar(
                f"Usuario: {pregunta}\nGEM: {respuesta}", coleccion="conversaciones"
            )
        except Exception as e:
            log.warning("No se pudo guardar conversación: %s", e)

    # ── API pública ──────────────────────────────────────────────────

    async def procesar_texto(self, texto: str) -> str:
        return await self._pipeline(texto)

    async def registrar_identidad(self) -> bool:
        return self._vision.registrar_desde_camara()

    async def guardar_contexto(self, texto: str, coleccion: str = "proyectos") -> None:
        await self._memoria.guardar(texto, coleccion=coleccion)

    def silenciar(self, valor: bool = True) -> None:
        self._silenciado = valor

    def get_estado(self) -> dict:
        return {
            "vision":           self._vision.get_estado(),
            "procesando":       self._procesando,
            "silenciado":       self._silenciado,
            "historial_turnos": len(self._historial) // 2,
            "memoria":          self._memoria.estadisticas(),
            "emocion_gem":      self._emocion_gem,
        }
