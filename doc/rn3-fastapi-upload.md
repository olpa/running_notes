# rn3-fastapi-upload

Implements the FastAPI backend for audio upload (ticket #3).

## What was built

- `backend/main.py` — FastAPI app
- `backend/requirements.txt` — pinned dependencies
- `backend/Dockerfile` — Python 3.12-slim image
- `docker-compose.yml` — added `backend` service on port 8000 with `./data` volume
- `data/` — directory for note storage (gitignored except `.gitkeep`)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{"status": "ok"}` |
| POST | `/record` | Accepts `file` upload, saves audio and metadata, returns metadata JSON |
| GET | `/note/{id}` | Returns metadata JSON for a note |
| GET | `/note/{id}/audio` | Serves the audio file |

## Storage layout

```
data/
  note-<12-hex>/
    audio.webm
    metadata.json
```

`metadata.json` fields: `id`, `created_at` (UTC ISO 8601), `subject`.

## How to run

```sh
docker compose up -d --build backend
curl http://localhost:8000/health
curl -F "file=@some.webm" http://localhost:8000/record
```
