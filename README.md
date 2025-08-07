# HR AI Assistant System 

A FastAPI-based system for CV/resume processing, analysis, and semantic search with PostgreSQL storage and LLaMA model integration.

## Features

- 🔐 User authentication with JWT tokens
- 📄 PDF CV processing and analysis
- 🔍 Semantic search using embeddings
- 💾 PostgreSQL database storage
- 👤 User-isolated data
- 💬 Chat-based CV querying
- 📊 Dashboard analytics

## System Architecture

```mermaid
graph TD
    U[User Message] --> A[Frontend]
    A -->|Send message| B[FastAPI Backend]
    
    B -->|Query| D[FAISS Vector Store]
    D -->|Retrieve CV Embeddings| C[PostgreSQL DB]
    
    C -->|Return CV Text| B
    B -->|Construct Prompt| E[Ollama 3.2]
    E -->|Answer| B
    B -->|Response| A
```

## Core Components

1. **Authentication System**
   - JWT-based authentication
   - User registration and login
   - Secure endpoints with token verification

2. **CV Processing Pipeline**
   - PDF upload and storage
   - Text extraction
   - LLaMA-based summarization
   - Embedding generation
   - Vector storage for semantic search

3. **Query System**
   - Natural language CV search
   - Semantic matching using embeddings
   - Chat-based interactions
   - History tracking

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user profile

### CV Management
- `GET /api/files` - List uploaded CVs
- `POST /api/upload` - Upload new CV
- `DELETE /api/files/{cv_id}` - Delete CV
- `GET /api/files/download/{cv_id}` - Download CV
- `GET /api/files/view/{cv_id}` - View CV in browser

### Search & Query
- `GET /query` - Search CVs with natural language
- `GET /candidates` - List candidates
- `GET /candidates/{cv_id}` - Get detailed candidate info

### Dashboard
- `GET /api/dashboard/stats` - Get usage statistics
- `GET /api/dashboard/recent` - Get recent activity
- `GET /api/chats` - View chat history

### System
- `POST /api/maintenance/rebuild-embeddings` - Rebuild embeddings
- `GET /health` - System health check
- `GET /` - API information

## Setup & Configuration

1. Install dependencies:
```bash
Download Ollama 3.2 and PostgreSQL
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
```env
DATABASE_URL=postgresql://"user":"password"@localhost:5432/hirelytic
JWT_SECRET_KEY=your_secret_key
```

3. Initialize the database and Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
when the server runs it will build the DB and boots the Ollama server

The api will run on `http://localhost:8000`

4. Start the Frontend:
```bash
cd "Front end"
npm install
npm run dev
```

## Security Considerations

- All endpoints except `/health` and `/` require authentication
- Files are stored with user isolation
- CORS is configured for security
- Database connections are pooled and managed
- JWT tokens are required for all protected endpoints

## Error Handling

The system includes comprehensive error handling for:
- File upload failures
- Processing errors
- Database connection issues
- Authentication failures
- Invalid requests

## Author

Anir Idhmad
