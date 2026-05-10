"""
Cliente unificado — AI Studio y Vertex AI.

  · AI Studio  (usar_vertex=False) → gemini_api_key requerida
  · Vertex AI  (usar_vertex=True)  → ADC (gcloud login o GOOGLE_APPLICATION_CREDENTIALS)

Capacidades:
  - generar_respuesta   → LLM
  - generar_embedding   → RAG
  - transcribir_audio   → STT (Gemini, funciona en ambos modos)
  - sintetizar_voz      → TTS (Cloud TTS en Vertex / Gemini TTS en AI Studio)
  - analizar_riesgo_comando
  - generar_correccion_comando
"""

import asyncio
import io
import re
import wave
import logging
import numpy as np
from google import genai
from google.genai import types
from backend.config import ajustes

log = logging.getLogger("gem.gemini")

_cliente: genai.Client | None = None


# ───────── Cliente ─────────

def _get_cliente() -> genai.Client:
    global _cliente
    if _cliente is None:
        if ajustes.usar_vertex:
            # La validación en config.py ya garantiza que vertex_project existe
            log.info(
                "Conectando a Vertex AI — proyecto=%s región=%s",
                ajustes.vertex_project,
                ajustes.vertex_location,
            )
            _cliente = genai.Client(
                vertexai=True,
                project=ajustes.vertex_project,
                location=ajustes.vertex_location,
            )
        else:
            # La validación en config.py ya garantiza que gemini_api_key existe
            log.info("Conectando a AI Studio")
            _cliente = genai.Client(api_key=ajustes.gemini_api_key)
    return _cliente


# ───────── LLM ─────────

def _historial_a_contents(historial: list[dict]) -> list[types.Content]:
    return [
        types.Content(
            role="user" if t["rol"] == "user" else "model",
            parts=[types.Part.from_text(text=t["texto"])],
        )
        for t in historial
    ]


async def generar_respuesta(historial: list[dict], system_prompt: str) -> str:
    cliente = _get_cliente()
    contents = _historial_a_contents(historial)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        max_output_tokens=1024,
    )

    def _llamar() -> str:
        resp = cliente.models.generate_content(
            model=ajustes.gemini_modelo,
            contents=contents,
            config=config,
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(_llamar)


# ───────── Embeddings ─────────

async def generar_embedding(texto: str) -> list[float]:
    cliente = _get_cliente()

    def _llamar() -> list[float]:
        resp = cliente.models.embed_content(
            model=ajustes.gemini_modelo_embedding,
            contents=texto,
        )
        if not resp.embeddings:
            raise RuntimeError("No se recibió embedding")
        return list(resp.embeddings[0].values)

    return await asyncio.to_thread(_llamar)


# ───────── STT ─────────

def _np_a_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    if audio.dtype != np.int16:
        audio_i16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    else:
        audio_i16 = audio
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(audio_i16.tobytes())
    return buf.getvalue()


async def transcribir_audio(audio: np.ndarray, sample_rate: int) -> str:
    """STT vía Gemini — funciona igual en AI Studio y Vertex AI."""
    cliente = _get_cliente()
    wav_bytes = _np_a_wav_bytes(audio, sample_rate)

    def _llamar() -> str:
        resp = cliente.models.generate_content(
            model=ajustes.gemini_modelo_stt,
            contents=[
                "Transcribe literalmente este audio en español. "
                "Devuelve SOLO el texto transcrito, sin comentarios ni marcas de tiempo. "
                "Si el audio está vacío o es ininteligible, responde con cadena vacía.",
                types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
            ],
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=512),
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(_llamar)


# ───────── TTS ─────────

def _cloud_tts(texto: str) -> tuple[np.ndarray, int]:
    """
    Google Cloud Text-to-Speech (modo Vertex AI).
    Usa ADC — no requiere API key adicional.
    """
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise RuntimeError(
            "Falta google-cloud-texttospeech. Ejecuta:\n"
            "  pip install google-cloud-texttospeech"
        )

    client = texttospeech.TextToSpeechClient()
    resp = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=texto),
        voice=texttospeech.VoiceSelectionParams(
            language_code=ajustes.tts_idioma,
            name=ajustes.tts_voz_cloud,
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=ajustes.tts_sample_rate,
        ),
    )
    # resp.audio_content = WAV completo con cabecera
    buf = io.BytesIO(resp.audio_content)
    with wave.open(buf, "rb") as w:
        pcm = w.readframes(w.getnframes())
        sr = w.getframerate()
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0, sr


def _gemini_tts(texto: str) -> tuple[np.ndarray, int]:
    """Gemini TTS (modo AI Studio). Requiere modelo con soporte de audio."""
    cliente = _get_cliente()
    resp = cliente.models.generate_content(
        model=ajustes.gemini_modelo_tts,
        contents=texto,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=ajustes.tts_voz,
                    )
                )
            ),
        ),
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0, ajustes.tts_sample_rate


async def sintetizar_voz(texto: str) -> tuple[np.ndarray, int]:
    """
    Sintetiza voz según el modo activo:
      · Vertex AI  → Google Cloud TTS (Neural2 en español)
      · AI Studio  → Gemini TTS preview
    """
    if not texto.strip():
        return np.zeros(0, dtype=np.float32), ajustes.tts_sample_rate

    def _llamar() -> tuple[np.ndarray, int]:
        try:
            if ajustes.usar_vertex:
                return _cloud_tts(texto)
            else:
                return _gemini_tts(texto)
        except Exception as e:
            log.error("TTS falló: %s", e)
            return np.zeros(0, dtype=np.float32), ajustes.tts_sample_rate

    return await asyncio.to_thread(_llamar)


# ───────── Riesgo de comandos PowerShell ─────────

_PROMPT_RIESGO = """Clasifica el riesgo del siguiente comando PowerShell.
Responde SOLO con una palabra: bajo, medio o alto.

bajo: lecturas, listados (Get-*, ls, dir).
medio: instalar software, modificar archivos del usuario.
alto: borrado masivo, registro, servicios críticos, -Force en rutas del sistema.

Comando: {comando}
Riesgo:"""


async def analizar_riesgo_comando(comando: str) -> str:
    cliente = _get_cliente()

    def _llamar() -> str:
        resp = cliente.models.generate_content(
            model=ajustes.gemini_modelo,
            contents=_PROMPT_RIESGO.format(comando=comando),
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=10),
        )
        texto = (resp.text or "").strip().lower()
        for nivel in ("alto", "medio", "bajo"):
            if nivel in texto:
                return nivel
        return "medio"

    return await asyncio.to_thread(_llamar)


# ───────── Auto-corrección PowerShell ─────────

_PROMPT_CORRECCION = """Eres experto en PowerShell. Un comando falló.
Devuelve SOLO el comando corregido, sin explicaciones ni backticks.

Comando original:
{comando}

Error:
{error}

Comando corregido:"""


def _limpiar_cmd(texto: str) -> str:
    texto = texto.strip()
    texto = re.sub(r"^```(?:powershell|ps1|pwsh)?\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


async def generar_correccion_comando(comando: str, error: str) -> str:
    cliente = _get_cliente()

    def _llamar() -> str:
        resp = cliente.models.generate_content(
            model=ajustes.gemini_modelo,
            contents=_PROMPT_CORRECCION.format(comando=comando, error=error),
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=512),
        )
        return _limpiar_cmd(resp.text or "")

    return await asyncio.to_thread(_llamar)
