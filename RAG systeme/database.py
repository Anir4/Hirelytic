"""
Database connection and models for CV Management System
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncpg
import asyncio
from contextlib import asynccontextmanager
import bcrypt
import jwt
from pydantic import BaseModel
import numpy as np
import secrets
from dotenv import load_dotenv

# Configuration
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Pydantic models for API
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

class CVCreate(BaseModel):
    filename: str
    original_text: Optional[str] = None
    summary_json: Optional[Dict[Any, Any]] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    candidate_phone: Optional[str] = None

class CVResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    candidate_name: Optional[str]
    candidate_email: Optional[str]
    candidate_phone: Optional[str]
    processing_status: str
    created_at: datetime
    updated_at: datetime

class ChatCreate(BaseModel):
    query: str
    query_type: str
    response_text: str
    cv_results: Optional[List[Dict]] = None

class ChatResponse(BaseModel):
    id: int
    user_id: int
    query: str
    query_type: str
    response_text: str
    cv_results: Optional[List[Dict]]
    created_at: datetime

# Database connection pool
_connection_pool = None

async def init_db_pool():
    """Initialize database connection pool"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    return _connection_pool

async def close_db_pool():
    """Close database connection pool"""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None

@asynccontextmanager
async def get_db_connection():
    """Get database connection from pool"""
    pool = await init_db_pool()
    async with pool.acquire() as connection:
        yield connection

# Database operations
class DatabaseManager:
    """Handles all database operations"""
    
    @staticmethod
    async def create_tables():
        """Create all database tables"""
        async with get_db_connection() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # CVs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cvs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    filename VARCHAR(255) NOT NULL,
                    original_text TEXT,
                    summary_json TEXT,
                    candidate_name VARCHAR(100),
                    candidate_email VARCHAR(100),
                    candidate_phone VARCHAR(20),
                    processing_status VARCHAR(50) DEFAULT 'uploaded',
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, filename)
                );
            """)
            
            # CV Embeddings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cv_embeddings (
                    id SERIAL PRIMARY KEY,
                    cv_id INTEGER REFERENCES cvs(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    embedding_data BYTEA NOT NULL,
                    embedding_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Chats table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    query TEXT NOT NULL,
                    query_type VARCHAR(50) NOT NULL,
                    response_text TEXT NOT NULL,
                    cv_results TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create indexes for better performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cvs_user_id ON cvs(user_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cvs_candidate_name ON cvs(candidate_name);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cv_embeddings_cv_id ON cv_embeddings(cv_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cv_embeddings_user_id ON cv_embeddings(user_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats(created_at);")
            
            print("✓ All database tables created successfully")
    
    # User operations
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    @staticmethod
    def create_jwt_token(user_id: int, username: str) -> str:
        """Create JWT token for user"""
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    async def create_user(username: str, email: str, password: str) -> Optional[int]:
        """Create new user"""
        async with get_db_connection() as conn:
            try:
                password_hash = DatabaseManager.hash_password(password)
                user_id = await conn.fetchval("""
                    INSERT INTO users (username, email, password_hash)
                    VALUES ($1, $2, $3)
                    RETURNING id
                """, username, email, password_hash)
                return user_id
            except asyncpg.UniqueViolationError:
                return None
    
    @staticmethod
    async def authenticate_user(username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user info"""
        async with get_db_connection() as conn:
            user = await conn.fetchrow("""
                SELECT id, username, email, password_hash
                FROM users WHERE username = $1
            """, username)
            
            if user and DatabaseManager.verify_password(password, user['password_hash']):
                return {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            return None
    
    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        async with get_db_connection() as conn:
            user = await conn.fetchrow("""
                SELECT id, username, email, created_at
                FROM users WHERE id = $1
            """, user_id)
            return dict(user) if user else None
    
    # CV operations
    @staticmethod
    async def create_cv(user_id: int, cv_data: CVCreate) -> Optional[int]:
        """Create new CV record"""
        async with get_db_connection() as conn:
            try:
                cv_id = await conn.fetchval("""
                    INSERT INTO cvs (user_id, filename, original_text, summary_json, 
                                   candidate_name, candidate_email, candidate_phone, processing_status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, user_id, cv_data.filename, cv_data.original_text,
                json.dumps(cv_data.summary_json) if cv_data.summary_json else None,
                cv_data.candidate_name, cv_data.candidate_email, 
                cv_data.candidate_phone, 'uploaded')
                return cv_id
            except asyncpg.UniqueViolationError:
                return None
    
    @staticmethod
    async def update_cv(cv_id: int, **kwargs) -> bool:
        """Update CV record"""
        async with get_db_connection() as conn:
            # Build dynamic update query
            set_clauses = []
            values = []
            param_count = 1
            
            for key, value in kwargs.items():
                if value is not None:
                    if key == 'summary_json':
                        value = json.dumps(value)
                    set_clauses.append(f"{key} = ${param_count}")
                    values.append(value)
                    param_count += 1
            
            if not set_clauses:
                return True
            
            set_clauses.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())
            values.append(cv_id)
            
            query = f"""
                UPDATE cvs 
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count + 1}
            """
            
            result = await conn.execute(query, *values)
            return result == "UPDATE 1"
    
    @staticmethod
    async def get_user_cvs(user_id: int, limit: int = 50, search: Optional[str] = None) -> List[Dict]:
        """Get user's CVs with optional search"""
        async with get_db_connection() as conn:
            if search:
                cvs = await conn.fetch("""
                    SELECT id, filename, candidate_name, candidate_email, candidate_phone,
                           processing_status, created_at, updated_at
                    FROM cvs 
                    WHERE user_id = $1 AND (
                        candidate_name ILIKE $2 OR 
                        candidate_email ILIKE $2 OR 
                        filename ILIKE $2
                    )
                    ORDER BY created_at DESC
                    LIMIT $3
                """, user_id, f"%{search}%", limit)
            else:
                cvs = await conn.fetch("""
                    SELECT id, filename, candidate_name, candidate_email, candidate_phone,
                           processing_status, created_at, updated_at
                    FROM cvs 
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
            
            return [dict(cv) for cv in cvs]
    
    @staticmethod
    async def get_cv_by_id(cv_id: int, user_id: int) -> Optional[Dict]:
        """Get CV by ID (user-scoped)"""
        async with get_db_connection() as conn:
            cv = await conn.fetchrow("""
                SELECT * FROM cvs 
                WHERE id = $1 AND user_id = $2
            """, cv_id, user_id)
            
            if cv:
                cv_dict = dict(cv)
                if cv_dict['summary_json']:
                    cv_dict['summary_json'] = json.loads(cv_dict['summary_json'])
                return cv_dict
            return None
    
    @staticmethod
    async def get_cv_by_filename(user_id: int, filename: str) -> Optional[Dict]:
        """Get CV by user_id and filename"""
        async with get_db_connection() as conn:
            cv = await conn.fetchrow("""
                SELECT id, user_id, filename, original_text, summary_json, 
                    candidate_name, candidate_email, candidate_phone, 
                    processing_status, file_size, created_at, updated_at
                FROM cvs 
                WHERE user_id = $1 AND filename = $2
            """, user_id, filename)
            
            if cv:
                cv_dict = dict(cv)
                # Parse JSON summary if it exists
                if cv_dict['summary_json']:
                    try:
                        cv_dict['summary_json'] = json.loads(cv_dict['summary_json'])
                    except json.JSONDecodeError:
                        cv_dict['summary_json'] = None
                return cv_dict
            return None
    
    @staticmethod
    async def delete_cv(cv_id: int, user_id: int) -> bool:
        """Delete CV and its embeddings"""
        async with get_db_connection() as conn:
            async with conn.transaction():
                # Delete embeddings first
                await conn.execute("""
                    DELETE FROM cv_embeddings 
                    WHERE cv_id = $1 AND user_id = $2
                """, cv_id, user_id)
                
                # Delete CV
                result = await conn.execute("""
                    DELETE FROM cvs 
                    WHERE id = $1 AND user_id = $2
                """, cv_id, user_id)
                
                return result == "DELETE 1"
    
    # Embedding operations
    @staticmethod
    async def save_cv_embedding(cv_id: int, user_id: int, embedding: np.ndarray, embedding_text: str) -> Optional[int]:
        """Save CV embedding"""
        async with get_db_connection() as conn:
            embedding_bytes = embedding.astype(np.float32).tobytes()
            embedding_id = await conn.fetchval("""
                INSERT INTO cv_embeddings (cv_id, user_id, embedding_data, embedding_text)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, cv_id, user_id, embedding_bytes, embedding_text)
            return embedding_id
    
    @staticmethod
    async def get_user_embeddings(user_id: int) -> List[Dict]:
        """Get all embeddings for a user"""
        async with get_db_connection() as conn:
            embeddings = await conn.fetch("""
                SELECT e.id, e.cv_id, e.embedding_data, e.embedding_text,
                       c.filename, c.candidate_name
                FROM cv_embeddings e
                JOIN cvs c ON e.cv_id = c.id
                WHERE e.user_id = $1
                ORDER BY e.created_at DESC
            """, user_id)
            
            result = []
            for emb in embeddings:
                emb_dict = dict(emb)
                # Convert bytes back to numpy array
                emb_data = np.frombuffer(emb_dict['embedding_data'], dtype=np.float32)
                emb_dict['embedding'] = emb_data
                del emb_dict['embedding_data']  # Remove bytes
                result.append(emb_dict)
            
            return result
    
    @staticmethod
    async def delete_cv_embeddings(cv_id: int, user_id: int) -> bool:
        """Delete all embeddings for a CV"""
        async with get_db_connection() as conn:
            await conn.execute("""
                DELETE FROM cv_embeddings 
                WHERE cv_id = $1 AND user_id = $2
            """, cv_id, user_id)
            return True
    
    # Chat operations
    @staticmethod
    async def save_chat(user_id: int, chat_data: ChatCreate) -> Optional[int]:
        """Save chat interaction"""
        async with get_db_connection() as conn:
            chat_id = await conn.fetchval("""
                INSERT INTO chats (user_id, query, query_type, response_text, cv_results)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, user_id, chat_data.query, chat_data.query_type, 
            chat_data.response_text, json.dumps(chat_data.cv_results) if chat_data.cv_results else None)
            return chat_id
    
    @staticmethod
    async def get_user_chats(user_id: int, limit: int = 50) -> List[Dict]:
        """Get user's chat history"""
        async with get_db_connection() as conn:
            chats = await conn.fetch("""
                SELECT id, query, query_type, response_text, cv_results, created_at
                FROM chats 
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            
            result = []
            for chat in chats:
                chat_dict = dict(chat)
                if chat_dict['cv_results']:
                    chat_dict['cv_results'] = json.loads(chat_dict['cv_results'])
                result.append(chat_dict)
            
            return result
    
    @staticmethod
    async def get_user_stats(user_id: int) -> Dict:
        """Get user statistics"""
        async with get_db_connection() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT c.id) as total_cvs,
                    COUNT(DISTINCT CASE WHEN c.processing_status = 'fully_processed' THEN c.id END) as processed_cvs,
                    COUNT(DISTINCT e.id) as total_embeddings,
                    COUNT(DISTINCT ch.id) as total_chats
                FROM users u
                LEFT JOIN cvs c ON u.id = c.user_id
                LEFT JOIN cv_embeddings e ON u.id = e.user_id
                LEFT JOIN chats ch ON u.id = ch.user_id
                WHERE u.id = $1
            """, user_id)
            
            return dict(stats) if stats else {
                'total_cvs': 0, 'processed_cvs': 0, 
                'total_embeddings': 0, 'total_chats': 0
            }



def create_and_load_env():
    env_file = ".env"

    # Generate a secure JWT secret
    generated_jwt_secret = secrets.token_urlsafe(64)

    # Default environment values
    default_env = {
        "DATABASE_URL": "postgresql://postgres:anir@localhost:5432/AI_Assistant",
        "JWT_SECRET": generated_jwt_secret,
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRATION_HOURS": "24"
    }

    # Create or update .env file
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            for key, value in default_env.items():
                f.write(f"{key}={value}\n")
        print(".env file created with secure JWT_SECRET.")
    else:
        # Load existing values and update missing ones
        load_dotenv(dotenv_path=env_file)
        with open(env_file, "a") as f:
            for key, value in default_env.items():
                if not os.getenv(key):
                    f.write(f"{key}={value}\n")
                    print(f"{key} added to existing .env.")

    # Load environment variables
    load_dotenv(dotenv_path=env_file)

    # Assign to variables
    database_url = os.getenv("DATABASE_URL")
    jwt_secret = os.getenv("JWT_SECRET")
    jwt_algorithm = os.getenv("JWT_ALGORITHM")
    jwt_expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS"))

    return {
        "DATABASE_URL": database_url,
        "JWT_SECRET": jwt_secret,
        "JWT_ALGORITHM": jwt_algorithm,
        "JWT_EXPIRATION_HOURS": jwt_expiration_hours
    }

# Example usage
config = create_and_load_env()

# Initialize database on import
async def initialize_database():
    """Initialize database tables"""
    await DatabaseManager.create_tables()

if __name__ == "__main__":
    # Create tables when run directly
    create_and_load_env()
    asyncio.run(initialize_database())