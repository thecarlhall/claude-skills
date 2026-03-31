#!/usr/bin/env python3
"""
LevelUp email TTS pipeline.

Reads a JSON array of email objects from a file path passed as the first argument.

Each object must have:
  subject    (str)  email subject line
  date_str   (str)  ISO date, e.g. "2026-03-18"
  body_plain (str)  plain-text body (may be empty string)
  body_html  (str)  HTML body (may be empty string)

Run inside the kokoro-pdf-tts uv environment:
    cd ~/devel/kokoro-pdf-tts && \
        uv run python ~/.claude/skills/levelup-email-tts/scripts/run_tts.py /tmp/levelup_emails.json
"""
import sys, os, re, json, tempfile, subprocess
import torch
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, ID3NoHeaderError

PDF_TTS_DIR = os.path.expanduser("~/devel/kokoro-pdf-tts")
CLEANER_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR   = os.path.join(PDF_TTS_DIR, "audio", "levelup")

sys.path.insert(0, PDF_TTS_DIR)
sys.path.insert(0, CLEANER_DIR)

from pdf_tts     import extract_text_from_pdf, text_to_audio
from clean_email import clean_body, html_to_pdf

os.makedirs(AUDIO_DIR, exist_ok=True)

# Voice assignments per newsletter series.
# Matched against the start of the subject line (case-insensitive).
VOICE_MAP = [
    ("tbl:",            "af_heart"),     # The Better Leader — female
    ("friday forward",  "af_heart"),     # Friday Forward — female
]
DEFAULT_VOICE = "af_bella"              # fallback for unrecognised series

# Lazy-loaded 50/50 blend of am_michael + am_adam for Level Up Newsletter.
_LEVELUP_VOICE = None


def get_levelup_voice():
    """Return a blended voice tensor: am_michael 50% + am_adam 50%."""
    global _LEVELUP_VOICE
    if _LEVELUP_VOICE is None:
        from kokoro import KPipeline
        _pipe = KPipeline(lang_code="a")
        t1 = _pipe.load_voice("am_michael")
        t2 = _pipe.load_voice("am_adam")
        _LEVELUP_VOICE = 0.5 * t1 + 0.5 * t2
    return _LEVELUP_VOICE


def pick_voice(subject: str, sender: str = ""):
    s = subject.lower()
    for prefix, voice in VOICE_MAP:
        if s.startswith(prefix):
            return voice
    # Sender-based matching for Level Up Newsletter (70/30 male blend).
    if "level up newsletter" in sender.lower():
        return get_levelup_voice()
    return DEFAULT_VOICE


def slugify(s):
    s = re.sub(r'[^\w\s-]', '', s.lower())
    return re.sub(r'[\s_-]+', '-', s).strip('-')[:60]


def tag_mp3(path, subject, date_str, sender=""):
    """Write ID3 tags to the MP3 file."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags["TIT2"] = TIT2(encoding=3, text=subject)
    tags["TALB"] = TALB(encoding=3, text="LevelUp")
    tags["TCON"] = TCON(encoding=3, text="Podcast")
    tags["TDRC"] = TDRC(encoding=3, text=date_str)
    if sender:
        tags["TPE1"] = TPE1(encoding=3, text=sender)
    tags.save(path, v2_version=4)


SCP_DEST = "carl@nuc:containers/audiobookshelf/podcasts/LevelUp/"


def upload_mp3(path):
    """Upload MP3 to audiobookshelf via SCP."""
    print(f"  Uploading to {SCP_DEST}...")
    result = subprocess.run(["scp", path, SCP_DEST], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Uploaded OK")
    else:
        print(f"  Upload failed: {result.stderr.strip()}")


def process_email(subject, date_str, body_plain, body_html, sender="", voice=None):
    slug     = f"{date_str}_{slugify(subject)}"
    out_path = os.path.join(AUDIO_DIR, f"{slug}.mp3")

    if os.path.exists(out_path):
        print(f"  Already exists, skipping: {out_path}")
        return out_path

    print(f"\nConverting: {subject}")

    # Route A: HTML -> PDF -> extract_text_from_pdf
    if body_html and len(body_html.strip()) >= 200:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_pdf = f.name
        try:
            html_to_pdf(body_html, tmp_pdf, subject=subject)
            text = extract_text_from_pdf(tmp_pdf)
        finally:
            try:
                os.unlink(tmp_pdf)
            except OSError:
                pass

    # Route B: plain-text fallback
    else:
        text = clean_body(plain=body_plain or "", html=body_html or "")

    if len(text) < 100:
        print(f"  Skipping '{subject}' -- cleaned body too short ({len(text)} chars)")
        return None

    chosen_voice = voice or pick_voice(subject, sender=sender)
    voice_label = "am_michael+am_adam(50/50)" if isinstance(chosen_voice, torch.FloatTensor) else chosen_voice
    print(f"  Text length: {len(text)} chars  |  voice: {voice_label}")
    text_to_audio(text, voice=chosen_voice, output_file=out_path)
    tag_mp3(out_path, subject=subject, date_str=date_str, sender=sender)
    print(f"  Saved: {out_path}")
    upload_mp3(out_path)
    return out_path


if len(sys.argv) < 2:
    print("Usage: run_tts.py <emails.json>", file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1]) as f:
    emails = json.load(f)
saved  = [process_email(**e) for e in emails]
print("\nDone:", [p for p in saved if p])
