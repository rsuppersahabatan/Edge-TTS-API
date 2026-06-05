from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, Security, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import edge_tts
import asyncio
import os
import secrets
import uuid
import wave
from datetime import datetime
from typing import Optional, List
import logging
import aiofiles

# Piper TTS is an optional, fully-local neural TTS engine. The import is guarded so
# the API still runs (with only the Edge engine) when piper-tts isn't installed or no
# voice models are present.
try:
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    try:
        # older piper-tts releases expose PiperVoice under piper.voice
        from piper.voice import PiperVoice
        PIPER_AVAILABLE = True
    except ImportError:
        PiperVoice = None
        PIPER_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ARSA Technology - Edge TTS API ~ Modified By mdestafadilah",
    description="Indonesian Text-to-Speech API using Microsoft Edge TTS",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OUTPUT_DIR = str(os.getenv("OUTPUT_DIR", "./app/output"))
MAX_TEXT_LENGTH = int(os.getenv("TTS_MAX_TEXT_LENGTH", "5000"))
CLEANUP_INTERVAL = int(os.getenv("TTS_CLEANUP_INTERVAL", "3600"))

# Authentication configuration
# Comma-separated list of valid API keys. If empty/unset, auth is DISABLED (dev mode).
API_KEYS = {k.strip() for k in os.getenv("API_KEYS", os.getenv("API_KEY", "")).split(",") if k.strip()}
API_KEY_HEADER_NAME = os.getenv("API_KEY_HEADER", "X-API-Key")
AUTH_ENABLED = len(API_KEYS) > 0

if AUTH_ENABLED:
    logger.info(f"API key authentication ENABLED ({len(API_KEYS)} key(s) loaded, header: {API_KEY_HEADER_NAME})")
else:
    logger.warning("API key authentication DISABLED — set API_KEY or API_KEYS env var to enable for production")

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

# Rate limiting configuration
# Per-route limits are configurable via env. Values use slowapi syntax: "<count>/<period>".
# Period: second, minute, hour, day. Examples: "30/minute", "1000/hour".
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
RATE_LIMIT_TTS = os.getenv("RATE_LIMIT_TTS", "30/minute")
RATE_LIMIT_TTS_BATCH = os.getenv("RATE_LIMIT_TTS_BATCH", "5/minute")
RATE_LIMIT_AUDIO = os.getenv("RATE_LIMIT_AUDIO", "120/minute")
RATE_LIMIT_STATS = os.getenv("RATE_LIMIT_STATS", "30/minute")
# Optional shared storage (e.g. "redis://host:6379"). Defaults to in-memory (per-process).
RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")


def rate_limit_key(request: Request) -> str:
    """Key requests by API key when present, otherwise by client IP.

    Per-key buckets let each authenticated caller have its own quota and prevent
    one noisy caller from starving others sharing the same egress IP.
    """
    key = request.headers.get(API_KEY_HEADER_NAME)
    if key:
        return f"key:{key}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri=RATE_LIMIT_STORAGE_URI,
    headers_enabled=True,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
logger.info(
    f"Rate limiting ENABLED (default={RATE_LIMIT_DEFAULT}, tts={RATE_LIMIT_TTS}, "
    f"batch={RATE_LIMIT_TTS_BATCH}, audio={RATE_LIMIT_AUDIO}, stats={RATE_LIMIT_STATS}, "
    f"storage={RATE_LIMIT_STORAGE_URI})"
)


async def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """Validate API key from request header. No-op when AUTH_ENABLED is False."""
    if not AUTH_ENABLED:
        return None
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing API key. Provide it via '{API_KEY_HEADER_NAME}' header.",
        )
    # constant-time comparison against each valid key to avoid timing leaks
    if not any(secrets.compare_digest(api_key, valid) for valid in API_KEYS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key


# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Indonesian voices configuration
INDONESIAN_VOICES = {
    "female": {
        "name": "id-ID-GadisNeural",
        "gender": "Female",
        "description": "Natural Indonesian female voice - Professional"
    },
    "male": {
        "name": "id-ID-ArdiNeural", 
        "gender": "Male",
        "description": "Natural Indonesian male voice - Authoritative"
    }
}

# English voices for international content
ENGLISH_VOICES = {
    "female_us": {
        "name": "en-US-AriaNeural",
        "gender": "Female",
        "description": "Natural US English female voice"
    },
    "male_us": {
        "name": "en-US-GuyNeural",
        "gender": "Male",
        "description": "Natural US English male voice"
    }
}

ALL_VOICES = {**INDONESIAN_VOICES, **ENGLISH_VOICES}

# ---------------------------------------------------------------------------
# Piper TTS (local neural engine) configuration
# ---------------------------------------------------------------------------
# Directory holding Piper voice models. Each voice is an ONNX model paired with a
# JSON config: e.g. "en_US-lessac-medium.onnx" + "en_US-lessac-medium.onnx.json".
# Download models from https://huggingface.co/rhasspy/piper-voices
PIPER_VOICES_DIR = str(os.getenv("PIPER_VOICES_DIR", "./app/piper_voices"))

# Map friendly voice ids to Piper model filenames (without the .onnx extension).
# Override/extend via the PIPER_VOICES env var as "id=model,id2=model2".
PIPER_VOICES = {
    "id_female": "id_ID-female-medium",
    "en_female": "en_US-lessac-medium",
    "en_male": "en_US-ryan-medium",
}
_piper_env = os.getenv("PIPER_VOICES", "").strip()
if _piper_env:
    for pair in _piper_env.split(","):
        if "=" in pair:
            vid, model = pair.split("=", 1)
            PIPER_VOICES[vid.strip()] = model.strip()

PIPER_DEFAULT_VOICE = os.getenv("PIPER_DEFAULT_VOICE", "en_female")

# Default engine used when a request doesn't specify one ("edge" or "piper").
# Configurable via the TTS_DEFAULT_ENGINE env var so deployments can flip the
# default without code changes.
SUPPORTED_ENGINES = {"edge", "piper"}
DEFAULT_ENGINE = os.getenv("TTS_DEFAULT_ENGINE", "edge").strip().lower()
if DEFAULT_ENGINE not in SUPPORTED_ENGINES:
    logger.warning(
        f"TTS_DEFAULT_ENGINE='{DEFAULT_ENGINE}' is not one of {sorted(SUPPORTED_ENGINES)}; falling back to 'edge'"
    )
    DEFAULT_ENGINE = "edge"
logger.info(f"Default TTS engine: {DEFAULT_ENGINE}")

# Cache of loaded PiperVoice objects (model loading is expensive, so reuse them).
_piper_voice_cache: dict = {}

if PIPER_AVAILABLE:
    logger.info(f"Piper TTS engine AVAILABLE (voices dir: {PIPER_VOICES_DIR}, {len(PIPER_VOICES)} voice(s) mapped)")
else:
    logger.warning("Piper TTS engine NOT available — install 'piper-tts' to enable the local engine")


def get_piper_voice(voice: str) -> "PiperVoice":
    """Load (and cache) a Piper voice model by its friendly id.

    Raises HTTPException with a clear message when Piper is unavailable or the
    requested model file cannot be found.
    """
    if not PIPER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Piper TTS engine is not installed. Run 'pip install piper-tts'.",
        )

    model_name = PIPER_VOICES.get(voice, PIPER_VOICES.get(PIPER_DEFAULT_VOICE))
    if model_name is None:
        raise HTTPException(status_code=400, detail=f"Unknown Piper voice '{voice}'.")

    if model_name in _piper_voice_cache:
        return _piper_voice_cache[model_name]

    model_path = os.path.join(PIPER_VOICES_DIR, f"{model_name}.onnx")
    config_path = f"{model_path}.json"
    if not os.path.exists(model_path):
        raise HTTPException(
            status_code=503,
            detail=(
                f"Piper voice model '{model_name}.onnx' not found in {PIPER_VOICES_DIR}. "
                "Download it from https://huggingface.co/rhasspy/piper-voices"
            ),
        )

    config_arg = config_path if os.path.exists(config_path) else None
    loaded = PiperVoice.load(model_path, config_path=config_arg)
    _piper_voice_cache[model_name] = loaded
    logger.info(f"Loaded Piper voice model: {model_name}")
    return loaded


def synthesize_piper(text: str, voice: str, output_file: str) -> None:
    """Synthesize `text` to a WAV file at `output_file` using Piper (blocking)."""
    piper_voice = get_piper_voice(voice)
    with wave.open(output_file, "wb") as wav_file:
        piper_voice.synthesize(text, wav_file)

# Pydantic models
class TTSRequest(BaseModel):
    text: str
    voice: str = "female"
    rate: str = "+0%"  # -50% to +100%
    pitch: str = "+0Hz"  # -50Hz to +50Hz
    volume: str = "+0%"  # -50% to +50%
    language: str = "indonesian"  # indonesian or english
    output_format: str = "wav"  # wav or mp3
    # edge or piper (piper is local/offline and outputs wav only).
    # Defaults to TTS_DEFAULT_ENGINE from the environment.
    engine: str = DEFAULT_ENGINE

    class Config:
        schema_extra = {
            "example": {
                "text": "Selamat datang di ARSA Technology, perusahaan AI terdepan di Indonesia",
                "voice": "female",
                "rate": "+10%",
                "pitch": "+25Hz",
                "language": "indonesian"
            }
        }

class TTSResponse(BaseModel):
    success: bool
    message: str
    audio_id: str
    audio_url: str
    duration_estimate: Optional[float] = None
    voice_used: str
    file_size: Optional[int] = None

class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    gender: str
    description: str
    language: str
    engine: str = "edge"

# Utility functions
def estimate_duration(text: str, language: str = "indonesian") -> float:
    """Estimate audio duration based on text length and language"""
    word_count = len(text.split())
    # Indonesian: ~120 words/minute, English: ~150 words/minute
    words_per_minute = 120 if language.lower() == "indonesian" else 150
    duration_minutes = word_count / words_per_minute
    return round(duration_minutes * 60, 2)

def get_voice_name(voice: str, language: str) -> str:
    """Get the actual voice name for Edge TTS"""
    if language.lower() == "english":
        return ENGLISH_VOICES.get(voice, ENGLISH_VOICES["female_us"])["name"]
    else:
        return INDONESIAN_VOICES.get(voice, INDONESIAN_VOICES["female"])["name"]

async def cleanup_old_files():
    """Clean up audio files older than cleanup interval"""
    try:
        current_time = datetime.now().timestamp()
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.isfile(file_path) and filename.endswith(('.wav', '.mp3')):
                file_age = current_time - os.path.getctime(file_path)
                if file_age > CLEANUP_INTERVAL:
                    os.remove(file_path)
                    logger.info(f"Cleaned up old file: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning up files: {e}")

# API Routes
@app.get("/")
async def root():
    return {
        "service": "ARSA Technology Edge-TTS API",
        "version": "1.0.0",
        "status": "running",
        "supported_languages": ["Indonesian", "English"],
        "endpoints": {
            "tts": "/tts - Generate speech",
            "voices": "/voices - List available voices",
            "health": "/health - Health check",
            "stats": "/stats - Service statistics",
            "audio": "/audio/{audio_id} - Download audio",
            "docs": "/docs - API documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "edge-tts-api",
        "output_dir_writable": os.access(OUTPUT_DIR, os.W_OK),
        "auth_enabled": AUTH_ENABLED,
        "engines": {
            "edge": True,
            "piper": PIPER_AVAILABLE,
        },
    }

@app.get("/voices", response_model=List[VoiceInfo])
async def list_voices():
    """List all available voices"""
    voices = []
    
    # Indonesian voices
    for voice_id, voice_data in INDONESIAN_VOICES.items():
        voices.append(VoiceInfo(
            voice_id=voice_id,
            name=voice_data["name"],
            gender=voice_data["gender"],
            description=voice_data["description"],
            language="Indonesian"
        ))
    
    # English voices
    for voice_id, voice_data in ENGLISH_VOICES.items():
        voices.append(VoiceInfo(
            voice_id=voice_id,
            name=voice_data["name"], 
            gender=voice_data["gender"],
            description=voice_data["description"],
            language="English"
        ))

    # Piper (local) voices
    for voice_id, model_name in PIPER_VOICES.items():
        voices.append(VoiceInfo(
            voice_id=voice_id,
            name=model_name,
            gender="Unknown",
            description=f"Local Piper neural voice ({model_name})",
            language="Indonesian" if voice_id.startswith("id") else "English",
            engine="piper"
        ))

    return voices

@app.post("/tts", response_model=TTSResponse, dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT_TTS)
async def generate_speech(request: Request, tts_request: TTSRequest, background_tasks: BackgroundTasks):
    """Generate speech from text"""
    try:
        # Validate input
        if not tts_request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        if len(tts_request.text) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Text too long (max {MAX_TEXT_LENGTH} characters)"
            )

        engine = tts_request.engine.lower()

        # Generate unique ID for this audio
        audio_id = str(uuid.uuid4())

        if engine == "piper":
            # Piper is local/offline and only produces WAV output.
            voice_name = PIPER_VOICES.get(tts_request.voice, PIPER_VOICES.get(PIPER_DEFAULT_VOICE, tts_request.voice))
            filename = f"{audio_id}.wav"
            output_file = os.path.join(OUTPUT_DIR, filename)
            # synthesis is blocking, so offload it from the event loop
            await asyncio.to_thread(synthesize_piper, tts_request.text, tts_request.voice, output_file)
        else:
            # Get voice name
            voice_name = get_voice_name(tts_request.voice, tts_request.language)

            # Determine file extension
            file_extension = "wav" if tts_request.output_format.lower() == "wav" else "mp3"
            filename = f"{audio_id}.{file_extension}"
            output_file = os.path.join(OUTPUT_DIR, filename)

            # Create TTS communicate object
            communicate = edge_tts.Communicate(
                text=tts_request.text,
                voice=voice_name,
                rate=tts_request.rate,
                pitch=tts_request.pitch,
                volume=tts_request.volume
            )

            # Generate and save audio
            await communicate.save(output_file)

        # Verify file was created
        if not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Failed to generate audio file")

        # Get file size
        file_size = os.path.getsize(output_file)

        # Estimate duration
        duration = estimate_duration(tts_request.text, tts_request.language)
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_old_files)
        
        logger.info(f"Generated audio: {audio_id} for voice: {voice_name}, size: {file_size} bytes")
        
        return TTSResponse(
            success=True,
            message="Audio generated successfully",
            audio_id=audio_id,
            audio_url=f"/audio/{audio_id}",
            duration_estimate=duration,
            voice_used=voice_name,
            file_size=file_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate speech: {str(e)}")

@app.get("/audio/{audio_id}", dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT_AUDIO)
async def download_audio(request: Request, audio_id: str):
    """Download generated audio file"""
    try:
        for ext, media_type in (("wav", "audio/wav"), ("mp3", "audio/mpeg")):
            file_path = os.path.join(OUTPUT_DIR, f"{audio_id}.{ext}")
            if os.path.exists(file_path):
                return FileResponse(
                    file_path,
                    media_type=media_type,
                    filename=f"arsa_tts_{audio_id}.{ext}"
                )

        raise HTTPException(status_code=404, detail="Audio file not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio download error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download audio")

@app.post("/tts/batch", dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT_TTS_BATCH)
async def generate_batch_speech(request: Request, requests: List[TTSRequest], background_tasks: BackgroundTasks):
    """Generate multiple speech files in batch"""
    try:
        if len(requests) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 requests per batch")
        
        results = []
        
        for req in requests:
            try:
                # Generate speech for each request
                audio_id = str(uuid.uuid4())
                engine = req.engine.lower()

                if engine == "piper":
                    voice_name = PIPER_VOICES.get(req.voice, PIPER_VOICES.get(PIPER_DEFAULT_VOICE, req.voice))
                    filename = f"{audio_id}.wav"
                    output_file = os.path.join(OUTPUT_DIR, filename)
                    await asyncio.to_thread(synthesize_piper, req.text, req.voice, output_file)
                else:
                    voice_name = get_voice_name(req.voice, req.language)

                    file_extension = "wav" if req.output_format.lower() == "wav" else "mp3"
                    filename = f"{audio_id}.{file_extension}"
                    output_file = os.path.join(OUTPUT_DIR, filename)

                    communicate = edge_tts.Communicate(
                        text=req.text,
                        voice=voice_name,
                        rate=req.rate,
                        pitch=req.pitch,
                        volume=req.volume
                    )

                    await communicate.save(output_file)
                
                file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
                duration = estimate_duration(req.text, req.language)
                
                results.append({
                    "success": True,
                    "audio_id": audio_id,
                    "audio_url": f"/audio/{audio_id}",
                    "duration_estimate": duration,
                    "voice_used": voice_name,
                    "file_size": file_size,
                    "text_preview": req.text[:50] + "..." if len(req.text) > 50 else req.text
                })
                
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "text_preview": req.text[:50] + "..." if len(req.text) > 50 else req.text
                })
        
        background_tasks.add_task(cleanup_old_files)
        
        return {
            "batch_success": True,
            "total_requests": len(requests),
            "successful": len([r for r in results if r.get("success")]),
            "failed": len([r for r in results if not r.get("success")]),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch TTS error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

@app.get("/stats", dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT_STATS)
async def get_stats(request: Request):
    """Get service statistics"""
    try:
        # Count files in output directory
        files = os.listdir(OUTPUT_DIR) if os.path.exists(OUTPUT_DIR) else []
        audio_files = [f for f in files if f.endswith(('.wav', '.mp3'))]
        
        # Calculate total size
        total_size = 0
        for f in audio_files:
            file_path = os.path.join(OUTPUT_DIR, f)
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        
        return {
            "total_audio_files": len(audio_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "available_voices": len(ALL_VOICES),
            "supported_languages": ["Indonesian", "English"],
            "max_text_length": MAX_TEXT_LENGTH,
            "cleanup_interval_hours": CLEANUP_INTERVAL / 3600,
            "output_directory": OUTPUT_DIR
        }
        
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8021)