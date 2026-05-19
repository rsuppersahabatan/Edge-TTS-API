from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts
import asyncio
import os
import uuid
from datetime import datetime
from typing import Optional, List
import logging
import aiofiles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ARSA Technology - Edge TTS API",
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

# Pydantic models
class TTSRequest(BaseModel):
    text: str
    voice: str = "female"
    rate: str = "+0%"  # -50% to +100%
    pitch: str = "+0Hz"  # -50Hz to +50Hz
    volume: str = "+0%"  # -50% to +50%
    language: str = "indonesian"  # indonesian or english
    output_format: str = "wav"  # wav or mp3

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
        "output_dir_writable": os.access(OUTPUT_DIR, os.W_OK)
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
    
    return voices

@app.post("/tts", response_model=TTSResponse)
async def generate_speech(request: TTSRequest, background_tasks: BackgroundTasks):
    """Generate speech from text"""
    try:
        # Validate input
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if len(request.text) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=400, 
                detail=f"Text too long (max {MAX_TEXT_LENGTH} characters)"
            )
        
        # Get voice name
        voice_name = get_voice_name(request.voice, request.language)
        
        # Generate unique ID for this audio
        audio_id = str(uuid.uuid4())

        # Determine file extension
        file_extension = "wav" if request.output_format.lower() == "wav" else "mp3"
        filename = f"{audio_id}.{file_extension}"
        output_file = os.path.join(OUTPUT_DIR, filename)
        
        # Create TTS communicate object
        communicate = edge_tts.Communicate(
            text=request.text,
            voice=voice_name,
            rate=request.rate,
            pitch=request.pitch,
            volume=request.volume
        )
        
        # Generate and save audio
        await communicate.save(output_file)
        
        # Verify file was created
        if not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Failed to generate audio file")
        
        # Get file size
        file_size = os.path.getsize(output_file)
        
        # Estimate duration
        duration = estimate_duration(request.text, request.language)
        
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

@app.get("/audio/{audio_id}")
async def download_audio(audio_id: str):
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

@app.post("/tts/batch")
async def generate_batch_speech(requests: List[TTSRequest], background_tasks: BackgroundTasks):
    """Generate multiple speech files in batch"""
    try:
        if len(requests) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 requests per batch")
        
        results = []
        
        for req in requests:
            try:
                # Generate speech for each request
                voice_name = get_voice_name(req.voice, req.language)
                audio_id = str(uuid.uuid4())

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

@app.get("/stats")
async def get_stats():
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