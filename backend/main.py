import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

DATA_DIR = Path("/data")

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/record", status_code=201)
async def record(file: UploadFile):
    note_id = f"note-{uuid.uuid4().hex[:12]}"
    note_dir = DATA_DIR / note_id
    note_dir.mkdir(parents=True, exist_ok=True)

    audio_path = note_dir / "audio.webm"
    audio_path.write_bytes(await file.read())

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = f"Voice note {created_at}"
    metadata = {"id": note_id, "created_at": created_at, "subject": subject}
    (note_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return metadata


@app.get("/note/{note_id}")
def get_note(note_id: str):
    meta_path = DATA_DIR / note_id / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    return json.loads(meta_path.read_text())


@app.get("/note/{note_id}/audio")
def get_audio(note_id: str):
    audio_path = DATA_DIR / note_id / "audio.webm"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(audio_path, media_type="audio/webm")
