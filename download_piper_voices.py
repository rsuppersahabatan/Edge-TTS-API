#!/usr/bin/env python3
"""Download Piper TTS voice models into the local voices directory.

Piper voices live on Hugging Face (rhasspy/piper-voices). Each voice is a pair of
files: the ONNX model (`<name>.onnx`) and its config (`<name>.onnx.json`). A voice
name encodes its location on the repo, e.g. ``id_ID-news_tts-medium`` maps to:

    en/en_US/lessac/medium/id_ID-news_tts-medium.onnx[.json]

Usage:
    # download the default set (the voices mapped in main.py's PIPER_VOICES)
    python download_piper_voices.py

    # download specific voices
    python download_piper_voices.py id_ID-news_tts-medium en_US-ryan-medium

    # list voices available in the repo (region/quality), then pick names
    python download_piper_voices.py --list

Env:
    PIPER_VOICES_DIR   target directory (default: ./app/piper_voices)
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICES_INDEX = f"{HF_BASE}/voices.json"

# Sensible defaults — keep in sync with PIPER_VOICES in main.py. Indonesian Piper
# voices are limited; override on the command line if you have a specific one.
DEFAULT_VOICES = [
    "id_ID-news_tts-medium",
    "en_US-ryan-medium",
]

VOICES_DIR = os.getenv("PIPER_VOICES_DIR", "./app/piper_voices")


def voice_to_repo_path(name: str) -> str:
    """Convert ``id_ID-news_tts-medium`` -> ``en/en_US/lessac/medium``."""
    parts = name.split("-")
    if len(parts) < 3:
        raise ValueError(
            f"Voice name '{name}' is not in the expected '<lang_REGION>-<name>-<quality>' form."
        )
    lang_region = parts[0]            # en_US
    quality = parts[-1]              # medium
    voice_id = "-".join(parts[1:-1])  # lessac (or multi-part names)
    lang = lang_region.split("_")[0]  # en
    return f"{lang}/{lang_region}/{voice_id}/{quality}"


def download(url: str, dest: str) -> None:
    """Stream a URL to a local file with a simple progress indicator."""
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "piper-voice-downloader"})
    with urllib.request.urlopen(req) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        read = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            read += len(chunk)
            if total:
                pct = read * 100 // total
                print(f"\r    {os.path.basename(dest)}: {pct:3d}% "
                      f"({read // 1024} / {total // 1024} KiB)", end="", flush=True)
    os.replace(tmp, dest)
    print()


def fetch_voice(name: str) -> bool:
    """Download the .onnx and .onnx.json for a single voice. Returns success."""
    repo_path = voice_to_repo_path(name)
    os.makedirs(VOICES_DIR, exist_ok=True)
    ok = True
    for suffix in (".onnx", ".onnx.json"):
        filename = f"{name}{suffix}"
        dest = os.path.join(VOICES_DIR, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"  ✓ {filename} already present, skipping")
            continue
        url = f"{HF_BASE}/{repo_path}/{filename}"
        print(f"  ↓ {url}")
        try:
            download(url, dest)
        except urllib.error.HTTPError as e:
            print(f"  ✗ failed ({e.code} {e.reason}) — check the voice name", file=sys.stderr)
            ok = False
            break
        except urllib.error.URLError as e:
            print(f"  ✗ network error: {e.reason}", file=sys.stderr)
            ok = False
            break
    return ok


def list_voices() -> None:
    """Print available voice names from the repo index."""
    req = urllib.request.Request(VOICES_INDEX, headers={"User-Agent": "piper-voice-downloader"})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    for key in sorted(data.keys()):
        info = data[key]
        lang = info.get("language", {}).get("name_native", "")
        print(f"  {key:40s} {lang}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Piper TTS voice models.")
    parser.add_argument("voices", nargs="*", help="voice names (e.g. id_ID-news_tts-medium)")
    parser.add_argument("--list", action="store_true", help="list available voices and exit")
    args = parser.parse_args()

    if args.list:
        list_voices()
        return 0

    voices = args.voices or DEFAULT_VOICES
    print(f"Target directory: {os.path.abspath(VOICES_DIR)}")
    print(f"Downloading {len(voices)} voice(s): {', '.join(voices)}\n")

    failures = []
    for name in voices:
        print(f"• {name}")
        try:
            if not fetch_voice(name):
                failures.append(name)
        except ValueError as e:
            print(f"  ✗ {e}", file=sys.stderr)
            failures.append(name)
        print()

    if failures:
        print(f"Done with {len(failures)} failure(s): {', '.join(failures)}")
        print("Tip: run 'python download_piper_voices.py --list' to see valid names.")
        return 1
    print("All voices downloaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
