"""Speech helpers: xAI text-to-speech (/v1/tts) and speech-to-text (/v1/stt)."""

from __future__ import annotations

import os
import re

import httpx

XAI_API = "https://api.x.ai/v1"
VOICES = ["eve", "ara", "rex", "sal", "leo"]


def _stt_model() -> str:
    return os.getenv("XAI_STT_MODEL", "grok-voice-transcribe-2.0")


def _language() -> str:
    return os.getenv("XAI_TTS_LANGUAGE", "en")


def default_voice() -> str:
    return os.getenv("XAI_DEFAULT_VOICE", "eve")


def _headers() -> dict[str, str]:
    key = os.getenv("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not set. Add it to your .env file.")
    return {"Authorization": f"Bearer {key}"}


def speakable(text: str) -> str:
    """Drop *actions* so only the spoken words are read out."""
    return re.sub(r"\s+", " ", re.sub(r"\*[^*]*\*", " ", text)).strip()


INLINE_TAGS = {"pause", "long-pause", "laugh", "chuckle", "giggle", "cry", "tsk", "tongue-click",
               "lip-smack", "breath", "inhale", "exhale", "sigh", "hum-tune"}
WRAP_TAGS = {"soft", "whisper", "loud", "build-intensity", "decrease-intensity", "higher-pitch",
             "lower-pitch", "slow", "fast", "sing-song", "singing", "emphasis"}
MIN_SPEED, MAX_SPEED = 0.7, 1.5  # the range the API accepts
FILLERS = {"um", "uh", "hmm", "mm", "er", "ah"}  # hesitations the director may add
MP3_BYTES_PER_SECOND = 128_000 / 8  # xAI default output: 128 kbps MP3


def _words(text: str) -> list[str]:
    no_tags = re.sub(r"\[[a-z-]+\]|</?[a-z-]+>", " ", text)
    return re.sub(r"[^a-z0-9']+", " ", no_tags.lower()).split()


def clean_delivery(original: str, marked: str) -> str | None:
    """Accept the marked-up text only if it uses valid tags and keeps the exact spoken words."""
    spoken = speakable(original)
    for tag in re.findall(r"\[([^\]]*)\]", marked):
        if tag not in INLINE_TAGS:
            return None
    stack: list[str] = []
    for closing, tag in re.findall(r"<(/?)([a-z-]+)>", marked):
        if tag not in WRAP_TAGS:
            return None
        if not closing:
            stack.append(tag)
        elif not stack or stack.pop() != tag:
            return None
    drop = lambda ws: [w for w in ws if w not in FILLERS]  # fillers may be added, nothing else
    if stack or drop(_words(marked)) != drop(_words(spoken)):
        return None
    return marked.strip()


def clip_seconds(mp3: bytes) -> float:
    return len(mp3) / MP3_BYTES_PER_SECOND


def speak(text: str, voice: str | None = None, speed: float = 1.0, marked_up: bool = False) -> bytes:
    """Return MP3 bytes for `text` (empty bytes if there is nothing to say).

    With marked_up=True the text already carries xAI speech tags and is sent as-is;
    otherwise *actions* are stripped so only the spoken words are read.
    """
    text = text.strip() if marked_up else speakable(text)
    if not text:
        return b""
    body = {"text": text, "voice_id": voice or default_voice(), "language": _language(),
            "speed": round(min(MAX_SPEED, max(MIN_SPEED, speed)), 2)}
    r = httpx.post(f"{XAI_API}/tts", headers=_headers(), timeout=60, json=body)
    r.raise_for_status()
    return r.content


def transcribe(audio: bytes, filename: str = "speech.wav", mime: str = "audio/wav") -> str:
    r = httpx.post(f"{XAI_API}/stt", headers=_headers(), timeout=60,
                   files={"file": (filename, audio, mime)}, data={"model": _stt_model()})
    r.raise_for_status()
    return r.json().get("text", "").strip()
