# FinVault AI / OCR RAG MVP

A lightweight local RAG MVP for reading text from uploaded PDFs and images.

The app runs the backend/frontend in Docker, keeps uploaded files and ChromaDB data locally, and uses a locally installed Ollama service for embeddings and chat. Ollama is not packaged inside Docker.

## What It Does

- Accepts only `.pdf`, `.png`, `.jpg`, `.jpeg`, and `.webp` uploads.
- Converts PDF pages to images, then applies OCR.
- Uses PaddleOCR for stronger OCR on photos, scanned pages, cut paper, and imperfect images.
- Stores one OCR record per image or PDF page in ChromaDB, without text chunking.
- Shows the extracted OCR text first, then asks the local LLM to interpret it.
- Tells the model not to invent missing text, numbers, dates, names, or amounts.
- Deletes uploaded documents and their Chroma records.

## Why The Repo Is Lightweight

The GitHub repo does not contain Ollama models, Docker image archives, uploads, or ChromaDB runtime data.

First-time users install Ollama locally and run:

```bash
./setup_models.sh
```

That downloads the required Ollama models onto the user's own machine.

## Requirements

- Ubuntu/Linux
- Docker
- Docker Compose plugin or legacy `docker-compose`
- Local Ollama installed and running at `http://localhost:11434`

## First-Time Setup

Clone the repo:

```bash
git clone https://github.com/kfl15/MVP_beta.git
cd MVP_beta
```

Install Ollama locally:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Check Ollama:

```bash
curl http://localhost:11434/api/tags
```

If that fails, start Ollama:

```bash
ollama serve
```

In another terminal, download the required models:

```bash
./setup_models.sh
```

Start the app:

```bash
./start_app.sh
```

Open:

```text
http://localhost:3000
```

Backend health:

```text
http://localhost:8000/health
```

## Models

Default local LLM:

```text
qwen2.5:0.5b
```

Default embedding model:

```text
nomic-embed-text
```

OCR engine:

```text
PaddleOCR
```

To use a different Ollama model:

```bash
OLLAMA_LLM_MODEL=your-model ./setup_models.sh
OLLAMA_LLM_MODEL=your-model ./start_app.sh
```

## Docker Services

```text
backend  -> FastAPI app, host network, port 8000
frontend -> nginx-served React app, port 3000
```

Ollama is local on the host machine, not a Docker service.

## Project Structure

```text
backend/                 FastAPI API, OCR indexing, RAG query logic
backend/loaders/         OCR loader for PDF pages and images
frontend/                React + Vite UI
docker/                  Docker Compose, Dockerfiles, nginx config
setup_models.sh          Pulls local Ollama models
start_app.sh             Checks Ollama, builds Docker, starts app
data/uploads/            Runtime uploads, ignored by Git
chroma_store/            Runtime ChromaDB data, ignored by Git
deliverables/            Optional offline artifacts, ignored by Git
```

## Backend API

```text
GET    /health
POST   /upload
POST   /chat
GET    /documents
DELETE /documents/{document_id}
```

## OCR Settings

These can be changed before starting the app:

```bash
OCR_LANG=en OCR_PDF_SCALE=2.5 OCR_MIN_WIDTH=1400 ./start_app.sh
```

Higher `OCR_PDF_SCALE` and `OCR_MIN_WIDTH` can improve OCR quality but use more CPU and memory.

## Local Backend Development

Using the existing virtual environment:

```bash
source /home/kflv/venvs/smart3_venv/bin/activate
cd backend
pip install -r requirements.txt
export OLLAMA_BASE_URL=http://localhost:11434
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Vite usually runs at:

```text
http://localhost:5173
```

## Important Ignore Rules

These are intentionally not committed:

```text
deliverables/
*.tar
*.zip
*.7z
chroma_store/
data/uploads/
frontend/node_modules/
frontend/dist/
docker/ollama/models/
```

## Notes

- Run local Ollama before starting Docker.
- Run `./setup_models.sh` before the first app start.
- The backend verifies required Ollama models at startup.
- The backend does not auto-pull models.
- The first OCR upload may take longer because PaddleOCR downloads its OCR model cache.
