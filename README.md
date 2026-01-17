# Local RAG MVP (Dockerized)

A fully local Retrieval-Augmented Generation (RAG) MVP built with a privacy-first design. This project ensures all operations are performed on local infrastructure, with no reliance on external APIs.

---

## Tech Stack

- **FastAPI** – Backend API
- **ChromaDB** – Vector database
- **Ollama** – Local LLM & embeddings
- **React + Vite** – Frontend UI
- **Docker & Docker Compose** – Orchestration

---

## Architecture Overview

The system architecture follows this flow:

Frontend → FastAPI → ChromaDB → Ollama

All inference, embeddings, and retrieval processes are executed locally, ensuring data privacy.

---

## Project Structure

- **backend/**: FastAPI app and RAG logic
- **frontend/**: React UI built with Vite
- **docker/**: Dockerfiles and docker-compose.yml for orchestration
- **data/uploads/**: Directory for user-uploaded documents (runtime)
- **chroma_store/**: Directory for the vector database (runtime)

> **Note**: `data/uploads/` and `chroma_store/` are runtime directories and are intentionally excluded from version control.

---

## Prerequisites

To run this project, ensure the following are installed:

- Docker + Docker Compose
- Ollama (locally installed or Docker-based)
- Node.js (required only for local frontend development)

---

## Running the Project

### Using Docker (Recommended)

1. Navigate to the `docker` directory:

   ```bash
   cd docker
   ```

2. Build and start the containers:

   ```bash
   docker compose up --build
   ```

3. Open your browser and visit: [http://localhost:3000](http://localhost:3000)

---

### Local Development Mode

#### Backend

1. Navigate to the `backend` directory:

   ```bash
   cd backend
   ```

2. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the FastAPI server:

   ```bash
   python app.py
   ```

   The backend will be available at: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Frontend

1. Navigate to the `frontend` directory:

   ```bash
   cd frontend
   ```

2. Install the required Node.js packages:

   ```bash
   npm install
   ```

3. Start the development server:

   ```bash
   npm run dev
   ```

   The frontend will be available at: [http://localhost:3000](http://localhost:3000)

---

## Additional Notes

- **Vector Data**: Stored locally using ChromaDB.
- **Model Management**: Models are dynamically pulled via Ollama.

### Future Enhancements

This MVP is designed to be easily extendable with features such as:

- Chat memory
- Streaming responses
- Authentication
- Multi-user support
