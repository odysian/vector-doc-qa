# Quaero - Document Intelligence Platform

AI-powered PDF question-answering using Retrieval Augmented Generation (RAG). Upload documents, ask questions, get answers with cited sources.

**Live Demo:** https://quaero.odysian.dev

## What It Does

- Upload PDF documents
- AI processes and chunks content
- Ask natural language questions
- Get accurate answers with source citations
- Chat history persists across sessions
- Secure authentication

## Tech Stack

**Backend:**
- FastAPI (Python)
- PostgreSQL with pgvector
- OpenAI API (embeddings)
- Anthropic API (Claude for RAG)
- JWT authentication with argon2
- Deployed on Render

**Frontend:**
- Next.js 15 with TypeScript
- Tailwind CSS v4
- Deployed on Vercel

**Database:**
- Supabase (PostgreSQL with pgvector)
- Schema-based isolation for multi-project sharing

## What I Learned

### RAG Architecture
- Vector embeddings represent semantic meaning of text
- Chunking strategy: 1000 chars with word boundaries preserves context
- Similarity search using cosine distance in pgvector
- Achieved 85%+ similarity for relevant chunks vs 45% for noise

### Security
- Magic bytes validation prevents malware uploads (checks file content, not just extension)
- JWT authentication with document ownership
- Input validation with Pydantic
- Rate limiting to control API costs

### TypeScript
- Type safety catches bugs at compile time
- Interfaces make API integration cleaner

### Database
- Schema-based isolation (`quaero` schema) shares Supabase with other projects
- pgvector is simpler than dedicated vector DB for this scale

### Key Insights
- Chunking is critical: too small loses context, too large reduces precision
- Prompt engineering prevents hallucinations (instruct AI to cite sources)

## Running Locally

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL with pgvector (or use Supabase)
- OpenAI API key
- Anthropic API key

### Backend Setup
```bash
# Clone and setup
git clone https://github.com/odysian/vector-doc-qa
cd vector-doc-qa/backend

# Virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit with DATABASE_URL, SECRET_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000
API docs at http://localhost:8000/docs

### Frontend Setup
```bash
# In new terminal
cd vector-doc-qa/frontend

# Install dependencies
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev
```

Frontend runs at http://localhost:3000

### Database (Docker)
```bash
# If you don't have PostgreSQL + pgvector locally
docker-compose up -d
```

Or use Supabase free tier (includes pgvector).


## How It Works

1. User uploads PDF → Extract text → Chunk into 1000-char segments
2. Generate embeddings with OpenAI → Store in PostgreSQL with pgvector
3. User asks question → Generate embedding → Similarity search
4. Retrieve top 5 chunks → Send to Claude → Get answer with citations

## Deployment

- **Frontend:** Vercel (auto-deploy from `main` branch)
- **Backend:** Render (free tier with cold starts)
- **Database:** Supabase (free PostgreSQL + pgvector)

## Challenges

- **Cold starts:** Free tier spins down after 15 min (30-60 sec first load)
- **Chunking strategy:** Increased from 500 to 1000 chars for better context
- **File security:** Check magic bytes (`%PDF`), not just extension

## Contact

**Chris**
- GitHub: [@odysian](https://github.com/odysian)
- Website: https://odysian.dev
- Email: c.colosimo@odysian.dev

## License

MIT License - feel free to use this as a learning reference.
