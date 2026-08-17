"""
AI service using Google Gemini.

Handles 3 features:
1. analyze_image()   - detect issues/problems in an inspection photo
2. compare_images()  - compare two photos (before/after) and report changes
3. ask_question()    - answer an inspector's question

IMPORTANT: Uses the official google-genai SDK, which supports the new
"AQ." auth-key format (raw REST calls reject those keys).

Install:  pip install google-genai --break-system-packages

Configure the API key via environment variable GEMINI_API_KEY, or edit
GEMINI_API_KEY below.
"""
import os
import base64
import io

# Load .env file so GEMINI_API_KEY (and other secrets) are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# API key - set via env var or hard-code here (keep private!)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = "gemini-3.5-flash-lite"

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
        return _client
    except Exception as e:
        print(f"[ai] could not init Gemini client: {e}")
        return None


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def _strip_data_url(b64: str) -> bytes:
    """Accepts a data URL or raw base64 and returns raw image bytes."""
    if not b64:
        return b""
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    try:
        return base64.b64decode(b64)
    except Exception:
        return b""


def _image_part(image_b64: str):
    from google.genai import types
    raw = _strip_data_url(image_b64)
    return types.Part.from_bytes(data=raw, mime_type="image/jpeg")


def _fast_config():
    """Config that minimises latency: minimal thinking + capped output."""
    try:
        from google.genai import types
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            max_output_tokens=800,
        )
    except Exception:
        return None


def analyze_image(image_b64: str, question: str = "") -> dict:
    """Detect issues/problems in an inspection photo."""
    client = _get_client()
    if client is None:
        return {"success": False, "message": "AI not configured. Add GEMINI_API_KEY."}
    try:
        prompt = (
            "You are a marine vessel inspection AI assistant. Analyse this inspection photo. "
            "Identify any visible problems, defects, or safety issues (rust, corrosion, cracks, "
            "leaks, damage, missing equipment, expired tags, etc.). "
        )
        if question:
            prompt += f"\nThe inspector is checking: \"{question}\". Focus your analysis on that.\n"
        prompt += (
            "\nRespond in this format:\n"
            "STATUS: (PASS or FAIL or ATTENTION)\n"
            "ISSUE: (short description of any problem, or 'None detected')\n"
            "DETAIL: (1-2 sentences of explanation)\n"
            "SEVERITY: (Low, Medium, High, or Critical)"
        )
        resp = client.models.generate_content(
            model=MODEL,
            contents=[_image_part(image_b64), prompt],
            config=_fast_config(),
        )
        text = resp.text or ""
        return {"success": True, "analysis": text, "raw": text}
    except Exception as e:
        return {"success": False, "message": f"AI analysis failed: {e}"}


def compare_images(before_b64: str, after_b64: str, context: str = "") -> dict:
    """Compare a before and after photo and report what changed."""
    client = _get_client()
    if client is None:
        return {"success": False, "message": "AI not configured. Add GEMINI_API_KEY."}
    try:
        prompt = (
            "You are a marine vessel inspection AI. Compare these two inspection photos of the "
            "same area taken at different times. The FIRST image is the earlier/reference photo, "
            "the SECOND is the newer photo. "
        )
        if context:
            prompt += f"Context: {context}. "
        prompt += (
            "Identify what has CHANGED - new damage, worsening rust/corrosion, new leaks, "
            "removed or added equipment, or improvements.\n\n"
            "Respond in this format:\n"
            "CHANGE_DETECTED: (YES or NO)\n"
            "WHAT_CHANGED: (short description, or 'No significant change')\n"
            "CONCERN: (Low, Medium, High, or Critical)\n"
            "DETAIL: (1-2 sentences)"
        )
        resp = client.models.generate_content(
            model=MODEL,
            contents=[_image_part(before_b64), _image_part(after_b64), prompt],
            config=_fast_config(),
        )
        text = resp.text or ""
        return {"success": True, "comparison": text, "raw": text}
    except Exception as e:
        return {"success": False, "message": f"AI comparison failed: {e}"}


def ask_question(question: str, context: str = "") -> dict:
    """Answer an inspector's question."""
    client = _get_client()
    if client is None:
        return {"success": False, "message": "AI not configured. Add GEMINI_API_KEY."}
    try:
        prompt = (
            "You are a helpful marine vessel inspection assistant. Answer the inspector's "
            "question clearly and concisely, based on standard maritime inspection practice "
            "(SOLAS, MARPOL, ISM, port state control, class requirements).\n\n"
        )
        if context:
            prompt += f"Context: {context}\n\n"
        prompt += f"Question: {question}"
        resp = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config=_fast_config(),
        )
        text = resp.text or ""
        return {"success": True, "answer": text}
    except Exception as e:
        return {"success": False, "message": f"AI question failed: {e}"}