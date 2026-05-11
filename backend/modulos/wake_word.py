"""
Detector por Actividad de Voz (VAD) con auto-calibración.

Al iniciar mide el ruido ambiente durante 1.5 s y fija el umbral
automáticamente en 3× el nivel de ruido del micrófono.
Esto evita tener que ajustar VAD_RMS_UMBRAL manualmente.

Solo dispara si la frase duró >= vad_min_frase_s de voz continua.
"""

import asyncio
import logging
import threading
import time
import numpy as np
import sounddevice as sd
from backend.config import ajustes

log = logging.getLogger("gem.vad")

_SILENCIO = "silencio"
_HABLANDO = "hablando"


class VADDetector:
    def __init__(self, callback, loop, mic_lock: threading.Lock, procesando_event: threading.Event):
        self._callback   = callback      # async def callback(audio_np)
        self._loop       = loop
        self._mic_lock   = mic_lock
        self._procesando = procesando_event
        self._activo     = False
        self._hilo: threading.Thread | None = None
        self._cooldown_hasta = 0.0
        self._umbral     = ajustes.vad_rms_umbral   # se sobreescribe en calibración
        self.on_estado_vad = None   # async def on_estado_vad(hablando: bool)

    # ─── API pública ────────────────────────────────────────────────

    def iniciar(self):
        self._activo = True
        self._hilo = threading.Thread(target=self._run, daemon=True)
        self._hilo.start()

    def detener(self):
        self._activo = False
        if self._hilo:
            self._hilo.join(timeout=2.0)

    def iniciar_cooldown(self):
        self._cooldown_hasta = time.time() + ajustes.fallback_cooldown_s

    # ─── Calibración ────────────────────────────────────────────────

    def _calibrar(self) -> float:
        """
        Mide el RMS ambiente durante 1.5 s (sin hablar) y devuelve
        umbral = max(ruido×3, 0.005).  Informa en log.
        """
        dur    = 1.5
        frames = int(dur * ajustes.sample_rate)
        try:
            audio = sd.rec(frames, samplerate=ajustes.sample_rate,
                           channels=1, dtype="float32", blocking=True)
            ruido = float(np.sqrt(np.mean(audio ** 2)))
            umbral = max(ruido * 3.0, 0.005)
            log.info(
                "VAD calibrado — ruido_ambiente=%.4f  umbral=%.4f  "
                "(ajusta VAD_RMS_UMBRAL en .env para sobreescribir)",
                ruido, umbral,
            )
            return umbral
        except Exception as e:
            log.warning("Calibración falló (%s), usando umbral del .env (%.4f)", e, self._umbral)
            return self._umbral

    # ─── Loop principal ──────────────────────────────────────────────

    def _notificar(self, hablando: bool):
        cb = self.on_estado_vad
        if cb and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(cb(hablando), self._loop)
            except Exception:
                pass

    def _disparar(self, audio_np: np.ndarray):
        self._procesando.set()
        def _limpiar(_):
            self._procesando.clear()
        try:
            f = asyncio.run_coroutine_threadsafe(self._callback(audio_np), self._loop)
            f.add_done_callback(_limpiar)
        except Exception as e:
            log.exception("VAD dispatch error: %s", e)
            self._procesando.clear()

    def _run(self):
        # Calibrar antes de abrir el stream continuo
        self._umbral = self._calibrar()

        chunk_dur    = 0.05   # 50 ms
        chunk_frames = int(chunk_dur * ajustes.sample_rate)
        silencio_max = max(1, int(ajustes.silence_duration_s / chunk_dur))
        max_chunks   = int(ajustes.max_grabacion_s / chunk_dur)
        min_chunks   = max(1, int(ajustes.vad_min_frase_s / chunk_dur))

        log.info(
            "VAD listo — umbral=%.4f  frase_mín=%.1fs  silencio=%.1fs",
            self._umbral, ajustes.vad_min_frase_s, ajustes.silence_duration_s,
        )

        estado = _SILENCIO
        buf: list[np.ndarray] = []
        chunks_silencio = 0
        stream = None

        while self._activo:

            # Pausa si hay comando en proceso o cooldown TTS
            if self._procesando.is_set() or time.time() < self._cooldown_hasta:
                _cerrar(stream); stream = None
                if estado == _HABLANDO:
                    self._notificar(False)
                estado = _SILENCIO; buf = []; chunks_silencio = 0
                time.sleep(0.08)
                continue

            # Abrir micrófono si hace falta
            if stream is None:
                try:
                    stream = sd.InputStream(
                        samplerate=ajustes.sample_rate,
                        channels=1, dtype="float32",
                        blocksize=chunk_frames,
                    )
                    stream.start()
                except Exception as e:
                    log.error("VAD: no pudo abrir mic: %s", e)
                    time.sleep(1.0); continue

            # Leer chunk
            try:
                frame, _ = stream.read(chunk_frames)
            except Exception as e:
                log.debug("VAD read error: %s", e)
                _cerrar(stream); stream = None; continue

            rms     = float(np.sqrt(np.mean(frame.flatten() ** 2)))
            hay_voz = rms > self._umbral

            if estado == _SILENCIO:
                if hay_voz:
                    estado = _HABLANDO
                    buf    = [frame.flatten()]
                    chunks_silencio = 0
                    self._notificar(True)

            elif estado == _HABLANDO:
                buf.append(frame.flatten())
                if hay_voz:
                    chunks_silencio = 0
                else:
                    chunks_silencio += 1
                    if chunks_silencio >= silencio_max:
                        voz_chunks = len(buf) - chunks_silencio
                        self._notificar(False)
                        if voz_chunks >= min_chunks:
                            log.info("VAD: frase %.1fs → pipeline", voz_chunks * chunk_dur)
                            self._disparar(np.concatenate(buf))
                        else:
                            log.debug("VAD: descartada (%.1fs < %.1fs mín)",
                                      voz_chunks * chunk_dur, ajustes.vad_min_frase_s)
                        estado = _SILENCIO; buf = []; chunks_silencio = 0
                        continue

                # Seguridad: frase demasiado larga
                if len(buf) >= max_chunks:
                    self._notificar(False)
                    self._disparar(np.concatenate(buf))
                    estado = _SILENCIO; buf = []; chunks_silencio = 0

        _cerrar(stream)


def _cerrar(stream):
    if stream is None: return
    try:
        if stream.active: stream.stop()
        stream.close()
    except Exception:
        pass
