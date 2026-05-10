"""
Configuración central de GEM.

Modos:
  · AI Studio  → USAR_VERTEX=false  +  GEMINI_API_KEY=<key>
  · Vertex AI  → USAR_VERTEX=true   +  VERTEX_PROJECT=<project-id>
                 (auth: gcloud auth application-default login)
"""

import logging
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
_ENV_PATH = RAIZ_PROYECTO / ".env"

log = logging.getLogger("gem.config")


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ───── Modo ─────
    usar_vertex: bool    = Field(default=False)
    vertex_project: str  = Field(default="")
    vertex_location: str = Field(default="us-central1")

    # ───── AI Studio ─────
    gemini_api_key: str = Field(default="")

    # ───── Modelos ─────
    gemini_modelo: str           = "gemini-2.0-flash-001"
    gemini_modelo_stt: str       = "gemini-2.0-flash-001"
    gemini_modelo_tts: str       = "gemini-2.5-flash-preview-tts"
    gemini_modelo_embedding: str = "text-embedding-004"

    # ───── TTS ─────
    tts_voz: str         = "Kore"          # AI Studio
    tts_sample_rate: int = 24000
    tts_idioma: str      = "es-US"         # Vertex
    tts_voz_cloud: str   = "es-US-Neural2-A"

    # ───── FastAPI ─────
    fastapi_host: str = "127.0.0.1"
    fastapi_port: int = 8765

    # ───── Audio ─────
    sample_rate: int          = 16000
    silence_duration_s: float = 1.2    # silencio para dar la frase por terminada
    silence_threshold: float  = 0.012
    max_grabacion_s: float    = 15.0

    # ───── VAD (Voice Activity Detection) ─────
    # Reemplaza completamente openWakeWord.
    # El sistema escucha siempre; solo dispara cuando hay una frase
    # de al menos vad_min_frase_s segundos continuos de voz.
    vad_rms_umbral: float    = 0.012   # RMS mínimo para considerar que hay voz
                                        # (mismo valor que silence_threshold por defecto)
    vad_min_frase_s: float   = 0.8     # mínimo de voz continua para disparar
                                        # ruidos < 0.8s se ignoran
    fallback_cooldown_s: float = 5.0   # pausa post-TTS para no re-activar con la propia voz

    # ───── Visión ─────
    mediapipe_model_path: str = str(RAIZ_PROYECTO / "assets" / "face_landmarker.task")
    identidad_umbral: float   = 0.85
    vision_fps: int           = 10

    # ───── Memoria ─────
    chromadb_path: str = str(RAIZ_PROYECTO / "data" / "chromadb")
    rag_top_k: int     = 5

    # ───── PowerShell ─────
    ps_max_retries: int = 3
    ps_timeout_s: int   = 60

    # ───── Avatar ─────
    avatar_path: str = str(RAIZ_PROYECTO / "assets" / "avatar")

    @model_validator(mode="after")
    def validar_y_loggear(self) -> "Ajustes":
        if not _ENV_PATH.exists():
            log.warning(
                ".env NO encontrado en %s — usando valores por defecto y vars del sistema",
                _ENV_PATH,
            )

        if self.usar_vertex:
            if not self.vertex_project:
                raise ValueError(
                    "\n\n"
                    "  ERROR: USAR_VERTEX=true pero VERTEX_PROJECT está vacío.\n"
                    "  Agrega en tu .env:\n"
                    "    VERTEX_PROJECT=nombre-de-tu-proyecto-gcp\n"
                    "  Y autentícate:\n"
                    "    gcloud auth application-default login\n"
                )
            log.info(
                "Modo VERTEX AI — proyecto='%s', región='%s'",
                self.vertex_project, self.vertex_location,
            )
        else:
            if not self.gemini_api_key:
                raise ValueError(
                    "\n\n"
                    "  ERROR: GEMINI_API_KEY vacía y USAR_VERTEX=false.\n\n"
                    "  Opción A — AI Studio (gratis):\n"
                    "    USAR_VERTEX=false\n"
                    "    GEMINI_API_KEY=AIza...\n"
                    "    (key en https://aistudio.google.com/apikey)\n\n"
                    "  Opción B — Vertex AI:\n"
                    "    USAR_VERTEX=true\n"
                    "    VERTEX_PROJECT=tu-proyecto-gcp\n"
                    "    (luego: gcloud auth application-default login)\n"
                )
            log.info("Modo AI STUDIO — API key configurada")

        log.info(
            "VAD — umbral=%.3f, frase_mín=%.1fs, silencio=%.1fs",
            self.vad_rms_umbral, self.vad_min_frase_s, self.silence_duration_s,
        )
        return self


ajustes = Ajustes()
