"""Local demo OCR handoff: Tesseract runs in the user's browser, not in Python.

This function is intentionally NOT an AI/vision call. The browser submits its
untrusted OCR observation to a separate authenticated API route. No extraction
is ever marked VERIFIED automatically, and raw documents are not transmitted to
an external Gemini API from this service.
"""
def extract_receipt(raw_bytes: bytes, mime_type: str, categories: list[dict]) -> dict:
    return {
        'status': 'MANUAL_REQUIRED',
        'provider': 'TESSERACT_BROWSER_PENDING',
        'data': {},
        'raw': {'note': 'OCR browser berjalan setelah file dibuat sebagai draft.'}
    }
