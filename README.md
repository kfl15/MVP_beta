# FinVault AI / Local RAG MVP

A fully local Retrieval-Augmented Generation (RAG) MVP for private accounting and business documents.

The app runs with Docker, stores documents locally, uses ChromaDB for vectors, and uses Ollama for both embeddings and chat generation.

## What It Does

- Upload `.pdf`, `.txt`, `.xlsx`, `.xls`, and `.docx` files.
- Extract and chunk document text.
- Create local embeddings with `nomic-embed-text`.
- Store vectors in local ChromaDB.
- Answer questions with `llama3.2:1b`.
- Show source filenames when the answer is supported.
- Return `I don't know based on the provided documents.` when the answer is not supported.
- Delete uploaded documents and their vectors.

## Why The Repo Is Lightweight

Ollama models and Docker image exports are not stored in GitHub.

Instead, first-time users run:

```bash
./setup_models.sh
```

That script downloads the required Ollama models on the user's machine.

## Tech Stack

- FastAPI backend
- React + Vite frontend
- ChromaDB vector store
- Ollama local LLM and embeddings
- Docker Compose
- Nginx for serving the frontend container

## Project Structure

```text
backend/                 FastAPI API and RAG logic
frontend/                React + Vite UI
docker/                  Docker Compose, Dockerfiles, nginx config
setup_models.sh          First-time Ollama model setup
data/uploads/            Runtime uploads, ignored by Git
chroma_store/            Runtime vector DB, ignored by Git
deliverables/            Optional offline artifacts, ignored by Git
```

## First-Time Setup

Requirements:

- Docker
- Docker Compose plugin, or legacy `docker-compose`

Clone the repo:

```bash
git clone https://github.com/kfl15/MVP_beta.git
cd MVP_beta
```

Download the required Ollama models:

```bash
./setup_models.sh
```

If port `11434` is busy, the script will try `11435` or `11436`. You can also choose a port manually:

```bash
OLLAMA_HOST_PORT=11435 ./setup_models.sh
```

Start the full app:

```bash
cd docker
docker compose up -d --build
```

If you used a custom Ollama host port during setup, use the same value when starting Docker Compose:

```bash
cd docker
OLLAMA_HOST_PORT=11435 docker compose up -d --build
```

If your machine uses legacy Compose, run:

```bash
cd docker
docker-compose up -d --build
```

Open the app:

```text
http://localhost:3000
```

Backend health:

```text
http://localhost:8000/health
```

Backend API docs:

```text
http://localhost:8000/docs
```

## Demo Login

```text
admin1@gmail.com / admin1@12
admin2@gmail.com / admin2@12
```

These are demo credentials only. Replace them before real use.

## Docker Services

```text
ollama   -> official ollama/ollama image, port 11434
backend  -> FastAPI app, port 8000
frontend -> nginx-served React app, port 3000
```

Ollama models are stored in the Docker volume:

```text
ollama_models
```

Uploaded files and Chroma data are mounted from:

```text
data/
chroma_store/
```

## Models

Default LLM:

```text
llama3.2:1b
```

Default embedding model:

```text
nomic-embed-text
```

You can override them before running `setup_models.sh`:

```bash
OLLAMA_LLM_MODEL=your-llm OLLAMA_EMBED_MODEL=your-embed ./setup_models.sh
```

If you change models, update the backend environment values in `docker/docker-compose.yml` too.

## Backend API

```text
GET    /health
POST   /upload
POST   /chat
GET    /documents
DELETE /documents/{document_id}
```

## Local Backend Development

Using the existing virtual environment:

```bash
source /home/kflv/venvs/smart3_venv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

For local backend runs outside Docker, make sure Ollama is reachable:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
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

- The backend verifies required Ollama models at startup.
- The backend does not auto-pull models.
- Run `./setup_models.sh` before starting the full app for the first time.
- Use GitHub Releases, not normal Git commits, for any future large offline image archives.
