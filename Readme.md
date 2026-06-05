# ARSA Edge-TTS API 🎤

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-green.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

**Professional Indonesian Text-to-Speech API** built by [ARSA Technology](https://arsa.technology) using Microsoft Edge TTS.

Perfect for content creators, developers, and businesses needing high-quality Indonesian voice synthesis for videos, applications, and automation workflows.

## ✨ Features

🇮🇩 **Native Indonesian Support** - Natural sounding Indonesian voices (female & male)  
🇺🇸 **English Support** - Professional US English voices  
🚀 **High Performance** - Fast generation with concurrent request handling  
📦 **Batch Processing** - Generate multiple audio files simultaneously  
🔄 **Auto Cleanup** - Automatic file management and cleanup  
📊 **Analytics** - Built-in statistics and monitoring  
🐳 **Docker Ready** - One-command deployment  
🌐 **Remote Access** - API accessible from anywhere  
📖 **Interactive Docs** - Auto-generated API documentation  
🏥 **Health Monitoring** - Built-in health checks and status monitoring  
🔑 **API Key Authentication** - Production-ready auth via `X-API-Key` header (single or multi-key)  
🛡️ **Rate Limiting** - Per-route quotas keyed by API key (fallback to IP), backed by in-memory or Redis  

## 🎯 Use Cases

- **Video Content Creation** - Generate narration for educational videos
- **E-Learning Platforms** - Create course audio in Indonesian
- **Marketing Automation** - Automated voice-overs for social media
- **Accessibility Tools** - Text-to-speech for Indonesian applications
- **IoT & AI Projects** - Voice responses for smart devices
- **Content Localization** - Convert text content to Indonesian audio

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
git clone https://github.com/arsa-technology/edge-tts-api.git
cd edge-tts-api
docker-compose up -d
```

### Option 2: Docker Run

```bash
docker run -d \
  --name arsa-edge-tts \
  -p 8021:8021 \
  -v $(pwd)/output:/app/output \
  arsa/edge-tts-api:latest
```

### Option 3: Local Development

```bash
git clone https://github.com/arsa-technology/edge-tts-api.git
cd edge-tts-api
pip install -r requirements.txt
python main.py
```

### Option 4: Nginx Configuration

#### Buat folder audio di aaPanel jika belum ada
``` mkdir -p /www/wwwroot/nama_project_tts/audio ```

#### Berikan izin akses penuh agar Docker bisa menulis dan Nginx bisa membaca
``` chmod -R 755 /www/wwwroot/nama_project_tts/audio ```
``` chown -R www:www /www/wwwroot/nama_project_tts/audio ```

#### Update Proxy
```bash
  location /audio/ {
      alias /www/wwwroot/nama_project_tts/audio/;
      add_header Access-Control-Allow-Origin *;
      add_header Cache-Control "public, max-age=86400";
      try_files $uri $uri/ =404;
  }
```

## 🎤 Available Voices

| Voice ID | Language | Gender | Description |
|----------|----------|--------|-------------|
| `female` | Indonesian | Female | Professional, clear pronunciation |
| `male` | Indonesian | Male | Authoritative, business tone |
| `female_us` | English | Female | Natural US English |
| `male_us` | English | Male | Professional US English |

## 📡 API Usage

> **Note**: When `API_KEY` is configured, add `-H "X-API-Key: <your-key>"` to every protected request. The examples below omit it for brevity — see [Authentication](#api-key-authentication) for details.

### Basic Indonesian TTS

```bash
curl -X POST http://localhost:8021/tts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "text": "Selamat datang di ARSA Technology, perusahaan AI terdepan di Indonesia",
    "voice": "female",
    "language": "indonesian"
  }'
```

### Advanced Parameters

```bash
curl -X POST http://localhost:8021/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "ARSA Technology menghadirkan solusi AI dengan akurasi 99,67 persen",
    "voice": "female",
    "rate": "+15%",
    "pitch": "+30Hz",
    "volume": "+10%",
    "language": "indonesian",
    "output_format": "wav"
  }'
```

### Batch Processing

```bash
curl -X POST http://localhost:8021/tts/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "text": "Selamat pagi, Indonesia!",
      "voice": "female",
      "language": "indonesian"
    },
    {
      "text": "Good morning, world!",
      "voice": "female_us", 
      "language": "english"
    }
  ]'
```

### Python Integration

```python
import requests

# Generate Indonesian speech
response = requests.post('http://localhost:8021/tts', json={
    "text": "Teknologi AI untuk masa depan Indonesia",
    "voice": "female",
    "rate": "+10%",
    "language": "indonesian"
})

result = response.json()
if result["success"]:
    # Download the audio file
    audio_response = requests.get(f"http://localhost:8021{result['audio_url']}")
    with open("output.wav", "wb") as f:
        f.write(audio_response.content)
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');
const fs = require('fs');

async function generateIndonesianTTS() {
  try {
    // Generate speech
    const response = await axios.post('http://localhost:8021/tts', {
      text: 'ARSA Technology menghadirkan inovasi AI terdepan',
      voice: 'female',
      rate: '+10%',
      language: 'indonesian'
    });

    if (response.data.success) {
      // Download audio
      const audioResponse = await axios.get(
        `http://localhost:8021${response.data.audio_url}`,
        { responseType: 'arraybuffer' }
      );
      
      fs.writeFileSync('output.wav', audioResponse.data);
      console.log('Audio generated successfully!');
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

generateIndonesianTTS();
```

## Offline Voice

Catatan pakai
Piper butuh file model voice (tidak terbundel). Unduh dari https://huggingface.co/rhasspy/piper-voices ke folder app/piper_voices/, misal en_US-lessac-medium.onnx + en_US-lessac-medium.onnx.json. Lalu panggil:


POST /tts
{ "text": "Halo dunia", "engine": "piper", "voice": "en_female" }
Nama voice di PIPER_VOICES default (id_female, en_female, en_male) hanya placeholder — sesuaikan ke nama model yang benar-benar Anda unduh (terutama untuk Bahasa Indonesia, cek voice id_ID-* yang tersedia di repo tersebut).

# 1. unduh voice default ke ./app/piper_voices (sekali saja)
docker compose run --rm piper-downloader

# unduh voice tertentu
docker compose run --rm piper-downloader id_ID-news_tts-medium en_US-ryan-medium

# lihat daftar voice
docker compose run --rm piper-downloader --list

# 2. jalankan API seperti biasa — model sudah ada di volume
docker compose up -d

## 🔑 Authentication & Rate Limiting

### API Key Authentication

Authentication is **opt-in via environment variable**:

- Set `API_KEY` (single) or `API_KEYS` (comma-separated) → auth **enabled**.
- Leave both empty → auth **disabled** (development mode; a warning is logged on startup).

Public endpoints (no key required): `GET /`, `GET /health`, `GET /voices`, `/docs`, `/redoc`.
Protected endpoints (key required): `POST /tts`, `POST /tts/batch`, `GET /audio/{id}`, `GET /stats`.

**Enable for production:**

```bash
# Generate a strong key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# .env
API_KEY=paste-the-generated-key-here
# or rotate / per-tenant
API_KEYS=key-for-mobile-app,key-for-internal-batch,key-for-partner-x
```

**Send the key on every protected request:**

```bash
curl -X POST http://localhost:8021/tts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: paste-the-generated-key-here" \
  -d '{"text": "Halo dunia", "voice": "female", "language": "indonesian"}'
```

```python
import os, requests
HEADERS = {"X-API-Key": os.environ["API_KEY"]}
r = requests.post("http://localhost:8021/tts", headers=HEADERS, json={
    "text": "Teknologi AI untuk masa depan Indonesia",
    "voice": "female",
    "language": "indonesian",
})
```

Verify auth status from the public health check:

```bash
curl http://localhost:8021/health
# { "status": "healthy", ..., "auth_enabled": true }
```

Responses on failure: `401 Unauthorized` (header missing) · `403 Forbidden` (key invalid).
Keys are compared in constant time (`secrets.compare_digest`) to avoid timing leaks.

### Rate Limiting

All routes are rate-limited via [slowapi](https://github.com/laurentS/slowapi). Limits are keyed by **API key when present, otherwise client IP** — so each authenticated caller gets its own quota and one noisy IP cannot starve others.

**Default per-route limits** (override via env, syntax `<count>/<period>`, period = `second|minute|hour|day`):

| Route | Env Var | Default |
|-------|---------|---------|
| Global default (all routes) | `RATE_LIMIT_DEFAULT` | `60/minute` |
| `POST /tts` | `RATE_LIMIT_TTS` | `30/minute` |
| `POST /tts/batch` | `RATE_LIMIT_TTS_BATCH` | `5/minute` |
| `GET /audio/{id}` | `RATE_LIMIT_AUDIO` | `120/minute` |
| `GET /stats` | `RATE_LIMIT_STATS` | `30/minute` |

Every response includes:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 27
X-RateLimit-Reset: 1716100000
```

When a limit is exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

**Multi-replica / multi-worker deployments:** the default in-memory store is per-process, so quotas won't be shared. Point all instances at Redis:

```bash
RATE_LIMIT_STORAGE_URI=redis://redis:6379
```

…and add a redis service in your compose file.

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_MAX_TEXT_LENGTH` | `5000` | Maximum characters per request |
| `TTS_CLEANUP_INTERVAL` | `3600` | File cleanup interval (seconds) |
| `PYTHONUNBUFFERED` | `1` | Python output buffering |
| `OUTPUT_DIR` | `./app/output` | Where generated audio is stored inside the container |
| `HOST_OUTPUT_DIR` | _(unset)_ | Host path bind-mounted to `OUTPUT_DIR` (used by `docker-compose.yml`) |
| `API_KEY` | _(empty)_ | Single API key. Empty = auth disabled (dev mode). |
| `API_KEYS` | _(empty)_ | Comma-separated keys (multi-tenant / rotation). Takes precedence over `API_KEY`. |
| `API_KEY_HEADER` | `X-API-Key` | HTTP header clients must use to send the key |
| `RATE_LIMIT_DEFAULT` | `60/minute` | Default limit for all routes |
| `RATE_LIMIT_TTS` | `30/minute` | Limit for `POST /tts` |
| `RATE_LIMIT_TTS_BATCH` | `5/minute` | Limit for `POST /tts/batch` |
| `RATE_LIMIT_AUDIO` | `120/minute` | Limit for `GET /audio/{id}` |
| `RATE_LIMIT_STATS` | `30/minute` | Limit for `GET /stats` |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | Storage for limiter; use `redis://host:6379` for multi-replica setups |

> See [`.env.example`](.env.example) for a ready-to-copy template.

### Docker Compose Configuration

```yaml
version: '3.8'
services:
  edge-tts:
    build: .
    ports:
      - "8021:8021"
    environment:
      - TTS_MAX_TEXT_LENGTH=5000
      - TTS_CLEANUP_INTERVAL=3600
      # Authentication (leave API_KEY empty to disable for dev)
      - API_KEY=${API_KEY:-}
      - API_KEYS=${API_KEYS:-}
      - API_KEY_HEADER=${API_KEY_HEADER:-X-API-Key}
      # Rate limiting
      - RATE_LIMIT_DEFAULT=${RATE_LIMIT_DEFAULT:-60/minute}
      - RATE_LIMIT_TTS=${RATE_LIMIT_TTS:-30/minute}
      - RATE_LIMIT_TTS_BATCH=${RATE_LIMIT_TTS_BATCH:-5/minute}
      - RATE_LIMIT_AUDIO=${RATE_LIMIT_AUDIO:-120/minute}
      - RATE_LIMIT_STATS=${RATE_LIMIT_STATS:-30/minute}
      - RATE_LIMIT_STORAGE_URI=${RATE_LIMIT_STORAGE_URI:-memory://}
    volumes:
      - ./output:/app/output
    restart: unless-stopped
```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/` | GET | Service information |
| `/health` | GET | Health check |
| `/voices` | GET | List available voices |
| `/tts` | POST | Generate single audio |
| `/tts/batch` | POST | Generate multiple audios |
| `/audio/{audio_id}` | GET | Download audio file |
| `/stats` | GET | Service statistics |
| `/docs` | GET | Interactive API documentation |

## 🧪 Testing

Run the comprehensive test suite:

```bash
# If auth is enabled on the server, export the key first:
export API_KEY=your-key-here       # Linux/Mac
$env:API_KEY = "your-key-here"     # Windows PowerShell

# Test locally
python test_client.py

# Test remote server
python test_client.py YOUR_SERVER_IP

# Expected output:
# ✅ Health Check: healthy
# ✅ Voice Listing: 4 voices available
# ✅ Indonesian TTS: Generated successfully
# ✅ English TTS: Generated successfully
# ✅ Batch TTS: 3/3 successful
# ✅ Service Stats: All metrics available
```

## 🌐 Remote Access Setup

### 1. Open Firewall Ports

```bash
# Ubuntu/Debian
sudo ufw allow 8021/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8021/tcp
sudo firewall-cmd --reload
```

### 2. Cloud Provider Configuration

**AWS Security Group:**
```
Type: Custom TCP
Port: 8021
Source: 0.0.0.0/0 (or specific IPs)
```

**Google Cloud Firewall:**
```bash
gcloud compute firewall-rules create edge-tts-api \
  --allow tcp:8021 \
  --source-ranges 0.0.0.0/0
```

### 3. Nginx Reverse Proxy (Optional)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location /api/tts/ {
        proxy_pass http://localhost:8021/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📈 Performance & Limitations

### Performance Metrics
- **Generation Speed**: ~2-5 seconds per 100 words
- **Concurrent Requests**: Handles multiple simultaneous requests
- **Memory Usage**: ~100-200MB per container
- **File Size**: ~1MB per minute of audio (WAV format)

### Limits
- **Text Length**: Max 5,000 characters per request (`TTS_MAX_TEXT_LENGTH`)
- **Batch Size**: Max 10 requests per batch
- **File Retention**: Auto-cleanup after 1 hour (`TTS_CLEANUP_INTERVAL`)
- **Request Throughput**: Per-key/IP rate limits — see [Rate Limiting](#rate-limiting) section above

### Supported Formats
- **Output**: WAV (default), MP3
- **Sample Rate**: 22kHz (Edge TTS default)
- **Channels**: Mono
- **Bit Depth**: 16-bit

## 🛠️ Development

### Project Structure
```
edge-tts-service/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── docker-compose.yml  # Service orchestration
├── test_client.py      # Test suite
├── .env               # Environment variables
└── output/            # Generated audio files
```

### Local Development

```bash
# Clone repository
git clone https://github.com/arsa-technology/edge-tts-api.git
cd edge-tts-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8021
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🔒 Security Considerations

### Production Deployment
- **Authentication**: ✅ Built-in — set `API_KEY` / `API_KEYS` (see [Authentication](#api-key-authentication) section)
- **Rate Limiting**: ✅ Built-in — per-key/IP throttling (see [Rate Limiting](#rate-limiting) section)
- **Input Validation**: Pydantic schema + length cap via `TTS_MAX_TEXT_LENGTH`
- **CORS**: Default is `allow_origins=["*"]` — restrict to your domains for browser clients
- **Network Security**: Terminate TLS at a reverse proxy (Nginx/Caddy) and restrict access by IP/firewall
- **Resource Limits**: Set container memory/CPU limits (see Docker example below)
- **Shared Rate Limit Store**: If you run multiple replicas, point `RATE_LIMIT_STORAGE_URI` at Redis so quotas are global

### Docker Security
```yaml
# Example production configuration
services:
  edge-tts:
    build: .
    user: "1000:1000"  # Non-root user
    read_only: true    # Read-only filesystem
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=100m
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support & Community

### Get Help
- 📖 **Documentation**: [API Docs](http://localhost:8021/docs)
- 🐛 **Issues**: [GitHub Issues](https://github.com/arsa-technology/edge-tts-api/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/arsa-technology/edge-tts-api/discussions)

### Commercial Support
For enterprise support, custom development, or consulting services:
- 🌐 **Website**: [arsa.technology](https://arsa.technology)
- 📧 **Email**: [support@arsa.technology](mailto:support@arsa.technology)
- 📱 **WhatsApp**: [Contact Us](https://wa.me/6282145676433)

## 🏢 About ARSA Technology

**ARSA Technology** is Indonesia's leading AI and IoT solutions provider, specializing in:
- 🤖 **Artificial Intelligence** - Face recognition, computer vision, NLP
- 🌐 **Internet of Things** - Industrial monitoring, smart city solutions
- 🏭 **Industry 4.0** - Manufacturing automation and optimization
- 🏥 **Digital Health** - Medical AI and self-service health platforms
- 🎓 **Virtual Reality** - Immersive training and simulation

**Trusted by**: Ministry of Defense of Indonesia, Indonesian National Police, and leading enterprises across Southeast Asia.

### Our Products
- **ARSACA**: Advanced vision AI analytics for human recognition and safety
- **AKSAYANA**: Vehicle analytics and license plate recognition
- **SYNAPTA**: Medical AI platform for diagnostics and health monitoring
- **ANIYATA**: VR solutions for industrial training and simulation

## 🌟 Showcase

### Real-World Implementations

**Video Content Creation**
```python
# Generate educational content in Indonesian
educational_script = """
Teknologi AI ARSA telah membantu berbagai industri di Indonesia. 
Dengan akurasi 99,67 persen dalam pengenalan wajah, 
sistem kami mengamankan fasilitas strategis negara.
"""

tts_response = requests.post('http://localhost:8021/tts', json={
    "text": educational_script,
    "voice": "female",
    "rate": "+10%",
    "language": "indonesian"
})
```

**Multilingual Content**
```python
# Create bilingual content for international audience
contents = [
    {
        "text": "Selamat datang di masa depan teknologi Indonesia",
        "voice": "female",
        "language": "indonesian"
    },
    {
        "text": "Welcome to the future of Indonesian technology", 
        "voice": "female_us",
        "language": "english"
    }
]

batch_response = requests.post('http://localhost:8021/tts/batch', json=contents)
```

## 🚀 Roadmap

### Current Version (v1.0)
- ✅ Indonesian and English TTS
- ✅ Batch processing
- ✅ Docker deployment
- ✅ Remote access
- ✅ Auto cleanup
- ✅ API key authentication (single + multi-key, constant-time compare)
- ✅ Per-route rate limiting (per-key/IP, in-memory or Redis-backed)

### Upcoming Features (v1.1)
- 🔄 **Regional Indonesian Dialects** - Javanese, Sundanese voices
- 🔑 **JWT/OAuth2** - Token-based auth as an alternative to API keys
- 📊 **Advanced Analytics** - Usage metrics and reporting per API key
- 🎛️ **Voice Customization** - Emotion and style controls
- 📱 **Mobile SDK** - iOS and Android libraries

### Future Releases (v2.0+)
- 🧠 **AI Voice Cloning** - Custom voice training
- 🎵 **SSML Support** - Advanced speech markup
- ☁️ **Cloud Integration** - AWS, GCP, Azure deployments
- 🔄 **Real-time Streaming** - Live TTS streaming

---

<div align="center">

**Made with ❤️ by ARSA Technology**

[🌐 Website](https://arsa.technology) • [📧 Email](mailto:hello@arsa.technology) • [📱 WhatsApp](https://wa.me/6285168623493)

⭐ **Star this repository if it helped you!** ⭐

</div>