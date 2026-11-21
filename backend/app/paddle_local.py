"""Optional isolated PaddleOCR process. Only local demo may invoke it."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

_lock=threading.Lock()
ROOT=Path(__file__).resolve().parents[2]

def interpreter():
    return ROOT/".venv-ocr"/("Scripts/python.exe" if os.name=="nt" else "bin/python")

def enabled():
    return os.getenv("MHS_ENABLE_PADDLE")=="1" and interpreter().is_file()

def recognize(raw,media_type):
    if not enabled():return None
    suffix={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","application/pdf":".pdf"}.get(media_type)
    if not suffix or not 0<len(raw)<=8*1024*1024:raise ValueError("Unsupported receipt")
    # Do not inherit MHS credentials or unrelated application settings.
    allow={"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","TMPDIR","USERPROFILE","HOME","APPDATA","LOCALAPPDATA","SYSTEMDRIVE","HOMEDRIVE","HOMEPATH","PROGRAMDATA","COMSPEC","PATHEXT","NUMBER_OF_PROCESSORS","LANG"}
    env={k:v for k,v in os.environ.items() if k.upper() in allow}
    env.update(PYTHONUTF8="1",OMP_NUM_THREADS="4",FLAGS_use_mkldnn="0")
    if not _lock.acquire(blocking=False):raise RuntimeError("PaddleOCR busy")
    try:
        with tempfile.TemporaryDirectory(prefix="mhs-paddle-") as root:
            source=Path(root)/("receipt"+suffix); output=Path(root)/"result.json"
            source.write_bytes(raw)
            subprocess.run([str(interpreter()),str(Path(__file__).with_name("paddle_worker.py")) ,str(source),str(output)],
                cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=300)
            if output.stat().st_size>100000:raise ValueError("Oversized OCR result")
            result=json.loads(output.read_text(encoding="utf-8"))
            text=result.get("text")
            score=result.get("confidence")
            if not isinstance(text,str) or not text.strip():raise ValueError("Empty OCR result")
            if not isinstance(score,(int,float)) or not 0<=score<=100:score=None
            return {"text":text[:8000],"confidence":score}
    finally:_lock.release()
