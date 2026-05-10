"""
Detector por Actividad de Voz (VAD).

Reemplaza completamente el sistema de wake word (openWakeWord / RMS fallback).

Lógica:
  1. Escucha el micrófono continuamente en chunks de 50ms.
  2. Cuando detecta voz (RMS > umbral) empieza a GRABAR y bufferear audio.
  3. Cuando hay silencio suficiente, revisa cuánto duró la frase:
       · Muy corta (< vad_min_frase_s) → descarta. Era tos, ruido, etc.
       · Larga enough                  → dispara callback con TODO el audio.
  4. Durante el cooldown post-TTS no escucha, para no re-triggear con la
     propia voz del asistente.

Callback: callback(audio_np: np.ndarray)  ← recibe el audio directamente.
"""

import logging
import threading
import time
import numpy as np
import sounddevice as sd
from backend.config import ajustes

log = logging.getLogger("gem.vad")

# Estados del detector
_SILENCIO  = "silencio"
_HABLANDO  = "hablando"


class VADDetector:
    def __init__(
        self,
        callback,                     # async def callback(audio_np: np.ndarray)
        loop,
        mic_lock: threading.Lock,
        procesando_event: threading.Event,
    ):
        self._callback       = callback
        self._loop           = loop
        self._mic_lock       = mic_lock
        self._procesando     = procesando_event
        self._activo         = False
        self._hilo: threading.Thread | None = None
        self._cooldown_hasta = 0.0    # timestamp hasta el que silencia el VAD

    # ─────────────────────────────────────────────
    #  API pública
    # ─────────────────────────────────────────────

    def iniciar(self):
        self._activo = True
        self._hilo = threading.Thread(target=self._loop_vad, daemon=True)
        self._hilo.start()
        log.info(
            "VAD iniciado — umbral=%.3f, frase_mín=%.1fs, silencio=%.1fs",
            ajustes.vad_rms_umbral,
            ajustes.vad_min_frase_s,
            ajustes.silence_duration_s,
        )

    def detener(self):
        self._activo = False
        if self._hilo:
            self._hilo.join(timeout=2.0)

    def iniciar_cooldown(self):
        """Llama esto antes de reproducir TTS para que VAD no se re-active."""
        self._cooldown_hasta = time.time() + ajustes.fallback_cooldown_s

    # ─────────────────────────────────────────────
    #  Loop principal
    # ─────────────────────────────────────────────

    def _loop_vad(self):
        chunk_dur    = 0.05                                      # 50 ms por chunk
        chunk_frames = int(chunk_dur * ajustes.sample_rate)
        silencio_max = max(1, int(ajustes.silence_duration_s / chunk_dur))
        max_chunks   = int(ajustes.max_grabacion_s / chunk_dur)

        umbral        = ajustes.vad_rms_umbral
        min_frase_chunks = max(1, int(ajustes.vad_min_frase_s / chunk_dur))

        estado          = _SILENCIO
        buffer: list[np.ndarray] = []
        chunks_silencio = 0

        stream = None

        while self._activo:
            # Esperamos si hay una petición en proceso
            if self._procesando.is_set():
                if stream:
                    _cerrar_stream(stream)
                    stream = None
                time.sleep(0.1)
                estado          = _SILENCIO
                buffer          = []
                chunks_silencio = 0
                continue

            # En cooldown (esperando a que termine el TTS)
            if time.time() < self._cooldown_hasta:
                if stream:
                    _cerrar_stream(stream)
                    stream = None
                time.sleep(0.05)
                estado          = _SILENCIO
                buffer          = []
                chunks_silencio = 0
                continue

            # Abrir micrófono si hace falta
            if stream is None:
                try:
                    with self._mic_lock:
                        stream = sd.InputStream(
                            samplerate=ajustes.sample_rate,
                            channels=1,
                            dtype="float32",
                            blocksize=chunk_frames,
                        )
                        stream.start()
                except Exception as e:
                    log.error("VAD: no se pudo abrir el mic: %s", e)
                    time.sleep(1.0)
                    continue

            # Leer chunk
            try:
                frame, _ = stream.read(chunk_frames)
            except Exception as e:
                log.debug("VAD: error leyendo mic: %s", e)
                _cerrar_stream(stream)
                stream = None
                continue

            flat = frame.flatten()
            rms  = float(np.sqrt(np.mean(flat ** 2)))
            hay_voz = rms > umbral

            # ── Máquina de estados ──
            if estado == _SILENCIO:
                if hay_voz:
                    estado          = _HABLANDO
                    buffer          = [flat]
                    chunks_silencio = 0
                    log.debug("VAD: voz detectada (rms=%.4f)", rms)

            elif estado == _HABLANDO:
                buffer.append(flat)

                if hay_voz:
                    chunks_silencio = 0
                else:
                    chunks_silencio += 1
                    if chunks_silencio >= silencio_max:
                        # Fin de frase: evaluar duración
                        duracion_chunks = len(buffer) - chunks_silencio
                        if duracion_chunks >= min_frase_chunks:
                            log.info(
                                "VAD: frase detectada — %.1f s de voz",
                                duracion_chunks * chunk_dur,
                            )
                            audio = np.concatenate(buffer)
                            self._disparar(audio)
                        else:
                            log.debug(
                                "VAD: frase descartada — %.1f s (mín %.1f s)",
                                duracion_chunks * chunk_dur,
                                ajustes.vad_min_frase_s,
                            )
                        estado          = _SILENCIO
                        buffer          = []
                        chunks_silencio = 0
                        continue

                # Seguridad: frase demasiado larga → forzar dispatch
                if len(buffer) >= max_chunks:
                    log.info("VAD: frase máxima alcanzada, disparando")
                    audio = np.concatenate(buffer)
                    self._disparar(audio)
                    estado          = _SILENCIO
                    buffer          = []
                    chunks_silencio = 0

        if stream:
            _cerrar_stream(stream)

    # ─────────────────────────────────────────────
    #  Dispatch
    # ─────────────────────────────────────────────

    def _disparar(self, audio_np: np.ndarray):
        """Envía el audio capturado al orquestador de forma thread-safe."""
        import asyncio

        self._procesando.set()

        def _terminar(_future):
            self._procesando.clear()

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._callback(audio_np), self._loop
            )
            future.add_done_callback(_terminar)
        except Exception as e:
            log.exception("VAD: error disparando callback: %s", e)
            self._procesando.clear()


# ─────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────

def _cerrar_stream(stream):
    try:
        if stream.active:
            stream.stop()
        stream.close()
    except Exception:
        pass
