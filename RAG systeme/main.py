"""
Updated FastAPI application with PostgreSQL, user authentication, and JWT tokens
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import os
import json
from datetime import datetime
import shutil
import asyncio
from contextlib import asynccontextmanager
import llama_inference


# Import database and logic modules
from database import (
    DatabaseManager, UserCreate, UserLogin, UserResponse, 
    CVCreate, CVResponse, ChatCreate, ChatResponse,
    initialize_database, close_db_pool
)
from hr_assistant import HRAssistant
import faiss_store as vector_store
from extract_from_pdf import extract_text_from_pdf
from summarize_cv import summarize_cv


# Initialize FastAPI app

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events"""
    # Startup
    try:
        await initialize_database()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
    
    yield  # Application is running
    
    # Shutdown
    try:
        await close_db_pool()
        print("✓ Database connections closed")
    except Exception as e:
        print(f"✗ Error closing database connections: {e}")

app = FastAPI(
    title="CV Management System API with PostgreSQL",
    description="API for CV processing, querying, and management with user authentication",
    version="2.0.0",
    lifespan=lifespan
)

# Security
security = HTTPBearer()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directories (still needed for file storage)
DATA_DIR = "data"
PDFS_DIR = os.path.join(DATA_DIR, "pdfs")

# Ensure directories exist
os.makedirs(PDFS_DIR, exist_ok=True)

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Verify JWT token and return current user information.
    """
    try:
        # Extract token from Authorization header
        token = credentials.credentials
        
        # Verify token
        payload = DatabaseManager.verify_jwt_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user information
        user = await DatabaseManager.get_user_by_id(payload['user_id'])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/register", response_model=Dict)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        # Validate input
        if len(user_data.username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        
        if len(user_data.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        # Create user
        user_id = await DatabaseManager.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        
        if not user_id:
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Generate JWT token
        token = DatabaseManager.create_jwt_token(user_id, user_data.username)
        
        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "username": user_data.username,
            "access_token": token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/auth/login", response_model=Dict)
async def login_user(login_data: UserLogin):
    """Authenticate user and return JWT token"""
    try:
        # Authenticate user
        user = await DatabaseManager.authenticate_user(
            username=login_data.username,
            password=login_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Generate JWT token
        token = DatabaseManager.create_jwt_token(user['id'], user['username'])
        
        return {
            "message": "Login successful",
            "user_id": user['id'],
            "username": user['username'],
            "access_token": token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(**current_user)

# ============================================================================
# QUERY ENDPOINT (Updated with Authentication)
# ============================================================================

@app.get("/query")
async def query_cvs(
    q: str = Query(..., description="Search query for CVs"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Query CVs using natural language (user-specific)
    Example: /query?q=Find software engineers with Python experience
    """
    try:
        user_id = current_user['id']
        
        # Initialize HR Assistant for this user
        assistant = HRAssistant(user_id)
        await assistant.initialize()
        # Check if query is empty
        if not q.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Process the query
        response_text = await assistant.process_query(q)
        
        # Determine if it's a CV search query to provide additional data
        is_search_query = assistant.is_cv_search_query(q)
        cv_results = []
        total_matches = 0
        
        if is_search_query:
            # Get the raw CV search results for additional data
            top_k = assistant.extract_cv_count(q)
            raw_results = await vector_store.search_user_cvs(user_id, q, top_k)
            
            if raw_results:
                total_matches = len(raw_results)
                
                # Format CV results for API response
                for i, result in enumerate(raw_results):
                    cv_id = result.get('cv_id')
                    cv_summary = await assistant.load_cv_summary(cv_id) if cv_id else None
                    
                    if cv_summary:
                        # Extract key information for API response
                        cv_result = {
                            "rank": i + 1,
                            "similarity_score": result.get('similarity', 0.0),
                            "cv_id": cv_id,
                            "candidate_name": result.get('candidate_name', 'Unknown'),
                            "filename": result.get('filename', 'Unknown'),
                            "skills": cv_summary.get('Skills', [])[:10] if cv_summary.get('Skills') else [],
                            "experience": [],
                            "education": []
                        }
                        
                        # Format experience
                        if cv_summary.get('Experience'):
                            experiences = cv_summary['Experience']
                            if isinstance(experiences, list):
                                for exp in experiences[:2]:  # Top 2 experiences
                                    if isinstance(exp, dict):
                                        exp_item = {}
                                        if exp.get('Role'):
                                            exp_item['role'] = exp['Role']
                                        if exp.get('Company'):
                                            exp_item['company'] = exp['Company']
                                        if exp_item:
                                            cv_result["experience"].append(exp_item)
                        
                        # Format education
                        if cv_summary.get('Education'):
                            educations = cv_summary['Education']
                            if isinstance(educations, list):
                                for edu in educations[:2]:  # Top 2 education entries
                                    if isinstance(edu, dict):
                                        edu_item = {}
                                        if edu.get('Degree'):
                                            edu_item['degree'] = edu['Degree']
                                        if edu.get('School'):
                                            edu_item['school'] = edu['School']
                                        if edu_item:
                                            cv_result["education"].append(edu_item)
                        
                        cv_results.append(cv_result)
        
        # Build final response
        response = {
            "query": q,
            "query_type": "cv_search" if is_search_query else "general_chat",
            "response_text": response_text,
            "results": cv_results,
            "total_matches": total_matches,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

# ============================================================================
# FILE MANAGEMENT ENDPOINTS (Updated with Authentication)
# ============================================================================

@app.get("/api/files")
async def get_files(
    limit: Optional[int] = Query(50, description="Maximum number of files to return"),
    search: Optional[str] = Query(None, description="Search filter"),
    current_user: Dict = Depends(get_current_user)
):
    """Get list of user's uploaded files and their processing status"""
    try:
        user_id = current_user['id']
        
        # Get user's CVs from database
        cvs = await DatabaseManager.get_user_cvs(user_id, limit, search)
        
        files = []
        for cv in cvs:
            file_info = {
                "cv_id": cv['id'],
                "filename": cv['filename'],
                "candidate_name": cv['candidate_name'],
                "candidate_email": cv['candidate_email'],
                "candidate_phone": cv['candidate_phone'],
                "processing_status": cv['processing_status'],
                "uploaded_date": cv['created_at'].isoformat(),
                "updated_date": cv['updated_at'].isoformat()
            }
            files.append(file_info)
        
        return {
            "files": files,
            "total_count": len(files),
            "user_id": user_id,
            "search_query": search
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get files: {str(e)}")

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """Upload a new CV PDF file and process it through the complete pipeline"""
    try:
        user_id = current_user['id']
        
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Create unique filename to avoid conflicts between users
        base_name = os.path.splitext(file.filename)[0]
        unique_filename = f"user_{user_id}_{file.filename}"
        file_path = os.path.join(PDFS_DIR, unique_filename)
        
        # Check if CV already exists in database
        existing_cv = await DatabaseManager.get_cv_by_filename(user_id, file.filename)
        cv_id = None
        should_reprocess = False
        
        if existing_cv:
            cv_id = existing_cv['id']
            processing_status = existing_cv.get('processing_status', '')
            
            # Check if CV is fully processed
            if processing_status != 'fully_processed':
                print(f"🔄 Found existing CV with incomplete processing status: {processing_status}")
                print(f"🔄 Will reprocess CV ID {cv_id} from the beginning...")
                should_reprocess = True
                
                # Reset the CV record for reprocessing
                await DatabaseManager.update_cv(cv_id, 
                    original_text=None,
                    summary_json=None,
                    candidate_name=None,
                    candidate_email=None,
                    candidate_phone=None,
                    processing_status='uploading'
                )
                
                # Remove existing embedding if any
                try:
                    await DatabaseManager.delete_cv_embeddings(cv_id,user_id)
                    print(f"🗑️ Removed existing embedding for CV ID {cv_id}")
                except Exception as e:
                    print(f"⚠️ Could not remove existing embedding: {str(e)}")
                    
            else:
                # CV is already fully processed
                return {
                    "message": "CV already exists and is fully processed",
                    "cv_id": cv_id,
                    "filename": file.filename,
                    "candidate_name": existing_cv.get('candidate_name'),
                    "status": "fully_processed",
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "note": "File was already processed successfully"
                }
        
        # Save uploaded file (replace existing file if reprocessing)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(file_path)
        
        # Initialize processing status
        processing_status = {
            "uploaded": True,
            "extracted": False,
            "summarized": False,
            "embedded": False,
            "errors": []
        }
        
        # Create new CV record if it doesn't exist
        if not cv_id:
            cv_data = CVCreate(filename=file.filename)
            cv_id = await DatabaseManager.create_cv(user_id, cv_data)
            
            if not cv_id:
                raise HTTPException(status_code=400, detail=f"Failed to create CV record for '{file.filename}'")
            
            print(f"📝 Created new CV record with ID {cv_id}")
        else:
            print(f"♻️ Reprocessing existing CV with ID {cv_id}")
        
        try:
            # Step 1: Extract text from PDF
            print(f"🔍 Extracting text from {file.filename} for user {user_id}...")
            text_content = extract_text_from_pdf(file_path)
            
            if not text_content or not text_content.strip():
                raise Exception("No text could be extracted from the PDF")
            
            # Update CV record with extracted text
            await DatabaseManager.update_cv(cv_id, 
                original_text=text_content,
                processing_status='text_extracted'
            )
            
            processing_status["extracted"] = True
            print(f"✓ Text extracted and saved for CV ID {cv_id}")
            
        except Exception as e:
            error_msg = f"Text extraction failed: {str(e)}"
            processing_status["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            await DatabaseManager.update_cv(cv_id, processing_status='extraction_failed')
        
        try:
            # Step 2: Summarize CV using LLaMA
            if processing_status["extracted"]:
                print(f"🤖 Summarizing CV content for {file.filename}...")
                cv_summary = summarize_cv(text_content)
                print("----------------------------------------------------------------",cv_summary)
                if not cv_summary:
                    raise Exception("CV summarization returned empty result")
                
                if isinstance(cv_summary, dict) and cv_summary.get("raw", "").startswith("Error: Request timed out"):
                    raise Exception("CV summarization timed out. Please try uploading the file again.")
                
                # Extract candidate information from summary
                candidate_name = cv_summary.get('Name', 'Unknown')
                candidate_email = cv_summary.get('Email', '')
                candidate_phone = cv_summary.get('Phone', '')
                
                # Update CV record with summary and candidate info
                await DatabaseManager.update_cv(cv_id,
                    summary_json=cv_summary,
                    candidate_name=candidate_name,
                    candidate_email=candidate_email,
                    candidate_phone=candidate_phone,
                    processing_status='summarized'
                )
                
                processing_status["summarized"] = True
                print(f"✓ CV summarized and saved for CV ID {cv_id}")
                
        except Exception as e:
            error_msg = f"CV summarization failed: {str(e)}"
            processing_status["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            await DatabaseManager.update_cv(cv_id, processing_status='summarization_failed')
        
        try:
            # Step 3: Generate and store embedding
            if processing_status["summarized"]:
                print(f"📊 Generating embedding for {file.filename}...")
                
                # Process and store CV embedding
                success = await vector_store.process_and_store_cv(user_id, cv_id, cv_summary)
                
                if success:
                    await DatabaseManager.update_cv(cv_id, processing_status='fully_processed')
                    processing_status["embedded"] = True
                    print(f"✓ Embedding generated and stored for CV ID {cv_id}")
                else:
                    raise Exception("Failed to generate or store embedding")
                    
        except Exception as e:
            error_msg = f"Embedding generation failed: {str(e)}"
            processing_status["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            await DatabaseManager.update_cv(cv_id, processing_status='embedding_failed')
        
        # Determine overall status
        if processing_status["embedded"]:
            overall_status = "fully_processed"
        elif processing_status["summarized"]:
            overall_status = "partially_processed"
        elif processing_status["extracted"]:
            overall_status = "text_extracted_only"
        else:
            overall_status = "upload_only"
        
        # Final status update
        await DatabaseManager.update_cv(cv_id, processing_status=overall_status)
        
        # Prepare response
        response = {
            "message": "File uploaded and processed" + (" (reprocessed)" if should_reprocess else ""),
            "cv_id": cv_id,
            "filename": file.filename,
            "candidate_name": candidate_name if processing_status["summarized"] else None,
            "size": file_size,
            "status": overall_status,
            "processing_details": processing_status,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "reprocessed": should_reprocess
        }
        
        # Add warnings if there were errors
        if processing_status["errors"]:
            response["warnings"] = processing_status["errors"]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up uploaded file if processing completely failed
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        # Clean up database record if created and it's a new record (not reprocessing)
        if 'cv_id' in locals() and cv_id and not should_reprocess:
            try:
                await DatabaseManager.delete_cv(cv_id, user_id)
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"Upload and processing failed: {str(e)}")

@app.delete("/api/files/{cv_id}")
async def delete_file(
    cv_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """Delete a CV file and all associated data"""
    try:
        user_id = current_user['id']
        
        # Get CV info before deletion
        cv_data = await DatabaseManager.get_cv_by_id(cv_id, user_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="CV not found")
        
        # Delete from database (this will cascade to embeddings)
        success = await DatabaseManager.delete_cv(cv_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="CV not found or could not be deleted")
        
        # Clean up files from disk
        try:
            # Remove PDF file
            pdf_filename = f"user_{user_id}_{cv_data['filename']}"
            pdf_path = os.path.join(PDFS_DIR, pdf_filename)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                
        except Exception as e:
            print(f"Warning: Could not clean up files: {e}")
        
        return {
            "message": "CV deleted successfully",
            "cv_id": cv_id,
            "filename": cv_data['filename'],
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete CV: {str(e)}")

# ============================================================================
# DASHBOARD ENDPOINTS (Updated with Authentication)
# ============================================================================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: Dict = Depends(get_current_user)):
    """Get dashboard statistics for the current user"""
    try:
        user_id = current_user['id']
        
        # Get user statistics
        assistant = HRAssistant(user_id)

        stats = await assistant.get_user_stats()
        
        return {
            **stats,
            "user_id": user_id,
            "username": current_user['username']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/dashboard/recent")
async def get_recent_activity(current_user: Dict = Depends(get_current_user)):
    """Get recent activity for the current user"""
    try:
        user_id = current_user['id']
        
        # Get recent CVs
        recent_cvs = await DatabaseManager.get_user_cvs(user_id, limit=10)
        
        # Get recent chats
        recent_chats = await DatabaseManager.get_user_chats(user_id, limit=10)
        
        return {
            "recent_files": [
                {
                    "cv_id": cv['id'],
                    "filename": cv['filename'],
                    "candidate_name": cv['candidate_name'],
                    "uploaded_date": cv['created_at'].isoformat(),
                    "status": cv['processing_status']
                }
                for cv in recent_cvs
            ],
            "recent_queries": [
                {
                    "query": chat['query'],
                    "query_type": chat['query_type'],
                    "timestamp": chat['created_at'].isoformat()
                }
                for chat in recent_chats
            ],
            "user_id": user_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent activity: {str(e)}")

# ============================================================================
# CANDIDATES ENDPOINT (Updated with Authentication)
# ============================================================================

@app.get("/candidates")
async def get_candidates(
    limit: Optional[int] = Query(50, description="Maximum number of candidates to return"),
    search: Optional[str] = Query(None, description="Search filter for candidates"),
    current_user: Dict = Depends(get_current_user)
):
    """Get list of user's candidates with their basic information"""
    try:
        user_id = current_user['id']
        
        # Get user's CVs
        cvs = await DatabaseManager.get_user_cvs(user_id, limit, search)
        
        candidates = []
        for cv in cvs:
            # Get full CV data including summary
            cv_data = await DatabaseManager.get_cv_by_id(cv['id'], user_id)
            
            if cv_data:
                candidate = {
                    "cv_id": cv['id'],
                    "filename": cv['filename'],
                    "candidate_name": cv['candidate_name'] or 'Unknown',
                    "candidate_email": cv['candidate_email'] or '',
                    "candidate_phone": cv['candidate_phone'] or '',
                    "processing_status": cv['processing_status'],
                    "uploaded_date": cv['created_at'].isoformat(),
                    "skills": [],
                    "experience": [],
                    "education": []
                }
                
                # Add detailed info if summary exists
                if cv_data.get('summary_json'):
                    summary = cv_data['summary_json']
                    candidate["skills"] = summary.get('Skills', [])[:10]  # Top 10 skills
                    candidate["experience"] = summary.get('Experience', [])[:3]  # Top 3 experiences
                    candidate["education"] = summary.get('Education', [])[:3]  # Top 3 education entries
                
                candidates.append(candidate)
        
        return {
            "candidates": candidates,
            "total_count": len(candidates),
            "search_query": search,
            "user_id": user_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get candidates: {str(e)}")

@app.get("/candidates/{cv_id}")
async def get_candidate_detail(
    cv_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """Get detailed information for a specific candidate"""
    try:
        user_id = current_user['id']
        
        # Get full CV data
        cv_data = await DatabaseManager.get_cv_by_id(cv_id, user_id)
        
        if not cv_data:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Build response
        candidate = {
            "cv_id": cv_data['id'],
            "filename": cv_data['filename'],
            "candidate_name": cv_data['candidate_name'],
            "candidate_email": cv_data['candidate_email'],
            "candidate_phone": cv_data['candidate_phone'],
            "processing_status": cv_data['processing_status'],
            "uploaded_date": cv_data['created_at'].isoformat(),
            "updated_date": cv_data['updated_at'].isoformat(),
            "summary": cv_data.get('summary_json', {}),
            "original_text_preview": cv_data.get('original_text', '')[:500] + "..." if cv_data.get('original_text') else None
        }
        
        return candidate
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get candidate details: {str(e)}")

# ============================================================================
# CHAT HISTORY ENDPOINTS
# ============================================================================

@app.get("/api/chats")
async def get_chat_history(
    limit: Optional[int] = Query(50, description="Maximum number of chats to return"),
    current_user: Dict = Depends(get_current_user)
):
    """Get user's chat history"""
    try:
        user_id = current_user['id']
        
        chats = await DatabaseManager.get_user_chats(user_id, limit)
        
        return {
            "chats": chats,
            "total_count": len(chats),
            "user_id": user_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")

# ============================================================================
# SYSTEM MAINTENANCE ENDPOINTS
# ============================================================================

@app.post("/api/maintenance/rebuild-embeddings")
async def rebuild_user_embeddings(current_user: Dict = Depends(get_current_user)):
    """Rebuild all embeddings for the current user"""
    try:
        user_id = current_user['id']
        
        # Rebuild embeddings
        success = await vector_store.rebuild_user_embeddings(user_id)
        
        if success:
            return {
                "message": "Embeddings rebuilt successfully",
                "user_id": user_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to rebuild embeddings")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rebuild embeddings: {str(e)}")


@app.get("/api/files/download/{cv_id}")
async def download_cv_file(
    cv_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """Download the original PDF file for a CV"""
    try:
        user_id = current_user['id']
        
        # Get CV info to verify ownership and get filename
        cv_data = await DatabaseManager.get_cv_by_id(cv_id, user_id)
        
        if not cv_data:
            raise HTTPException(status_code=404, detail="CV not found")
        
        # Construct file path
        filename = cv_data['filename']
        unique_filename = f"user_{user_id}_{filename}"
        file_path = os.path.join(PDFS_DIR, unique_filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="PDF file not found on server")
        
        # Return the file
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"inline; filename={filename}"  # Use "attachment" for download, "inline" for view
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve file: {str(e)}")

@app.get("/api/files/view/{cv_id}")
async def view_cv_file(
    cv_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """View the PDF file in browser (inline)"""
    try:
        user_id = current_user['id']
        
        # Get CV info to verify ownership and get filename
        cv_data = await DatabaseManager.get_cv_by_id(cv_id, user_id)
        
        if not cv_data:
            raise HTTPException(status_code=404, detail="CV not found")
        
        # Construct file path
        filename = cv_data['filename']
        unique_filename = f"user_{user_id}_{filename}"
        file_path = os.path.join(PDFS_DIR, unique_filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="PDF file not found on server")
        
        # Return the file for inline viewing
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve file: {str(e)}")

# ============================================================================
# HEALTH CHECK AND INFO ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "CV Management System API with PostgreSQL",
        "version": "2.0.0",
        "features": [
            "User authentication with JWT",
            "PostgreSQL database storage",
            "User-isolated data",
            "CV processing pipeline",
            "Semantic search with embeddings",
            "Chat history tracking"
        ],
        "endpoints": {
            "auth": {
                "register": "/auth/register",
                "login": "/auth/login",
                "profile": "/auth/me"
            },
            "main": {
                "query": "/query?q=your_question",
                "files": "/api/files",
                "upload": "/api/upload",
                "candidates": "/candidates",
                "chats": "/api/chats"
            },
            "dashboard": {
                "stats": "/api/dashboard/stats",
                "recent": "/api/dashboard/recent"
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        test_user = await DatabaseManager.get_user_by_id(1)
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "directories": {
            "pdfs": os.path.exists(PDFS_DIR),
        }
    }

llama_inference.start_server()

# ============================================================================
# RUN THE APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)