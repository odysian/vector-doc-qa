# Backend - Document Intelligence

FastAPI backend for document processing and RAG.

## Structure
```
app/
├── main.py           # FastAPI application
├── config.py         # Configuration
├── database.py       # Database connection
├── models.py         # SQLAlchemy models
├── api/              # API endpoints
├── schemas/          # Pydantic models
├── services/         # Business logic
└── utils/            # Helper functions
```

## Development

### Run server
```bash
uvicorn app.main:app --reload
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
