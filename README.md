# Document Intelligence Platform

AI-powered document Q&A system using RAG (Retrieval Augmented Generation).

## Features
- PDF upload and processing
- Semantic search with vector embeddings
- AI-powered Q&A with source citations

## Tech Stack
- **Backend:** FastAPI, PostgreSQL (pgvector), SQLAlchemy
- **AI:** OpenAI (embeddings), Anthropic (RAG)
- **Frontend:** Next.js, TypeScript (coming soon)

## Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (for frontend)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys
```

### Database Setup
```bash
docker-compose up -d
```

### Run Backend
```bash
cd backend
uvicorn app.main:app --reload
```

## Project Structure
- `backend/` - FastAPI application
- `frontend/` - Next.js application (coming soon)
- `docker-compose.yml` - PostgreSQL with pgvector
