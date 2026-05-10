# GEM — Asistente de IA Personal con Vertex AI

Asistente de voz con avatar animado, memoria RAG, visión por cámara y ejecución de comandos PowerShell.

## Arquitectura

```
Usuario habla → Wake Word → STT (Gemini) → LLM (Gemini) → TTS → Bocinas
                                                   ↕
                                            Memoria RAG
                                           (ChromaDB local)
```

## Modos de operación

### Opción A — Google AI Studio (más fácil)
Gratis para empezar, sin cuenta GCP.

### Opción B — Vertex AI (recomendado para producción)
Requiere proyecto Google Cloud. Ventajas:
- Mayor cuota y SLA
- TTS con voces Neural2 en español de México/EE.UU.
- Facturación y monitoreo enterprise

---

## Instalación

```bash
# 1. Clonar / descomprimir el proyecto
# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Inicializar
python inicializar.py
```

---

## Configuración

### AI Studio (Opción A)

1. Obtén tu API key en https://aistudio.google.com/apikey
2. Edita `.env`:
   ```env
   USAR_VERTEX=false
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODELO=gemini-2.5-flash
   GEMINI_MODELO_STT=gemini-2.5-flash
   ```

### Vertex AI (Opción B)

1. Habilita APIs en tu proyecto GCP:
   - **Vertex AI API**: `gcloud services enable aiplatform.googleapis.com`
   - **Cloud Text-to-Speech API**: `gcloud services enable texttospeech.googleapis.com`

2. Configura autenticación:
   ```bash
   # Opción 1 — usuario local (desarrollo)
   gcloud auth application-default login

   # Opción 2 — service account (producción)
   export GOOGLE_APPLICATION_CREDENTIALS=/ruta/service-account.json
   ```

3. Edita `.env`:
   ```env
   USAR_VERTEX=true
   VERTEX_PROJECT=mi-proyecto-gcp
   VERTEX_LOCATION=us-central1

   GEMINI_MODELO=gemini-2.0-flash-001
   GEMINI_MODELO_STT=gemini-2.0-flash-001

   TTS_IDIOMA=es-US
   TTS_VOZ_CLOUD=es-US-Neural2-A
   ```

---

## Ejecutar

```bash
python -m backend.main
```

Frontend (opcional — Tauri):
```bash
cd src-tauri && cargo tauri dev
```

WebSocket de estado: `ws://127.0.0.1:8765/ws`

---

## Wake word

Por defecto usa **openWakeWord** (código abierto, gratis).

Frases detectadas: `"hey jarvis"`, `"alexa"`, `"hey mycroft"`, `"ok nabu"`

Si openWakeWord no está disponible, activa automáticamente el **fallback RMS** (detecta voz por volumen).

---

## Voces TTS disponibles (Vertex AI)

| Nombre | Género | Calidad |
|--------|--------|---------|
| es-US-Neural2-A | Femenino | ⭐⭐⭐⭐⭐ |
| es-US-Neural2-B | Masculino | ⭐⭐⭐⭐⭐ |
| es-US-Neural2-C | Femenino | ⭐⭐⭐⭐⭐ |
| es-US-Wavenet-A | Femenino | ⭐⭐⭐⭐ |
| es-US-Wavenet-B | Masculino | ⭐⭐⭐⭐ |

Más voces en: https://cloud.google.com/text-to-speech/docs/voices

---

## Endpoints REST

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servidor |
| GET | `/estado` | Estado del orquestador |
| POST | `/chat` | Enviar texto (sin voz) |
| POST | `/registrar_identidad` | Registrar cara del usuario |
| POST | `/guardar_contexto` | Añadir info a la memoria |
| POST | `/silenciar` | Silenciar/activar respuestas de voz |
| DELETE | `/historial` | Limpiar historial de conversación |
| WS | `/ws` | WebSocket bidireccional |

