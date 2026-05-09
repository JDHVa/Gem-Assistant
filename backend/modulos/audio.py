import asyncio
import io
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import miniaudio
import edge_tts
from faster_whisper import WhisperModel
from backend.config import ajustes


class ModuloAudio:
    def __init__(self, callback_activado, loop: asyncio.AbstractEventLoop):
        self._callback = callback_activado
        self._loop = loop
        self._modelo_wake = WhisperModel("tiny", device="cpu", compute_type="int8")
        self._modelo_stt = WhisperModel("base", device="cpu", compute_type="int8")
        self._activo = False
        self._hilo: threading.Thread | None = None

    def iniciar(self):
        self._activo = True
        self._hilo = threading.Thread(target=self._loop_wake_word, daemon=True)
        self._hilo.start()

    def detener(self):
        self._activo = False

    def _loop_wake_word(self):
        chunk_frames = int(ajustes.chunk_duration_s * ajustes.sample_rate)
        while self._activo:
            try:
                audio = sd.rec(
                    chunk_frames,
                    samplerate=ajustes.sample_rate,
                    channels=1,
                    dtype="int16",
                )
                sd.wait()
                audio_f32 = audio.flatten().astype(np.float32) / 32768.0
                segments, _ = self._modelo_wake.transcribe(
                    audio_f32,
                    language="es",
                    beam_size=1,
                    vad_filter=True,
                )
                texto = "".join(seg.text for seg in segments).lower().strip()
                if any(frase in texto for frase in ajustes.wake_phrases):
                    asyncio.run_coroutine_threadsafe(self._callback(), self._loop)
            except Exception:
                continue

    def grabar_hasta_silencio(self) -> np.ndarray:
        chunk_frames = int(0.1 * ajustes.sample_rate)
        silencio_max = int(ajustes.silence_duration_s / 0.1)
        grabacion: list[np.ndarray] = []
        chunks_silencio = 0

        while True:
            chunk = sd.rec(
                chunk_frames,
                samplerate=ajustes.sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            flat = chunk.flatten()
            grabacion.append(flat)
            rms = float(np.sqrt(np.mean(flat**2)))
            if rms < ajustes.silence_threshold:
                chunks_silencio += 1
                if chunks_silencio >= silencio_max and len(grabacion) > 10:
                    break
            else:
                chunks_silencio = 0

        return np.concatenate(grabacion)

    def transcribir(self, audio: np.ndarray) -> str:
        segments, _ = self._modelo_stt.transcribe(
            audio,
            language="es",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        return "".join(seg.text for seg in segments).strip()

    def audio_a_bytes_wav(self, audio: np.ndarray) -> bytes:
        buffer = io.BytesIO()
        sf.write(buffer, audio, ajustes.sample_rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()

    async def sintetizar_y_reproducir(self, texto: str) -> bytes:
        comunicar = edge_tts.Communicate(texto, ajustes.tts_voz)
        mp3_buffer = io.BytesIO()
        async for chunk in comunicar.stream():
            if chunk["type"] == "audio":
                mp3_buffer.write(chunk["data"])

        mp3_bytes = mp3_buffer.getvalue()
        decoded = miniaudio.decode(
            mp3_bytes,
            output_format=miniaudio.SampleFormat.FLOAT32,
        )
        audio_f32 = np.array(decoded.samples, dtype=np.float32)
        if decoded.nchannels > 1:
            audio_f32 = audio_f32.reshape(-1, decoded.nchannels).mean(axis=1)

        sd.play(audio_f32, samplerate=decoded.sample_rate)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sd.wait)
        return mp3_bytes

    async def sintetizar_a_bytes(self, texto: str) -> bytes:
        comunicar = edge_tts.Communicate(texto, ajustes.tts_voz)
        mp3_buffer = io.BytesIO()
        async for chunk in comunicar.stream():
            if chunk["type"] == "audio":
                mp3_buffer.write(chunk["data"])
        return mp3_buffer.getvalue()
