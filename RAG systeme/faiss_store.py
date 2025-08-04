"""
PostgreSQL-based vector store for CV embeddings
Replaces the FAISS-based approach with database storage
"""
import os
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity
import embed_model
from database import DatabaseManager

class PostgreSQLVectorStore:
    """PostgreSQL-based vector store for CV embeddings with user isolation."""
    
    def __init__(self):
        """Initialize PostgreSQL vector store."""
        self.dimension = 384  # all-MiniLM-L6-v2 embedding dimension
    
    def create_embedding_text(self, cv_summary: dict) -> str:
        """
        Create focused text for embedding from CV summary.
        Combines Name, Experience, Skills, and Education fields.
        
        Args:
            cv_summary: Parsed CV summary JSON
            
        Returns:
            Combined text string for embedding
        """
        embedding_parts = []
        
        # Add Name
        if 'Name' in cv_summary and cv_summary['Name']:
            name = cv_summary['Name']
            if isinstance(name, str):
                embedding_parts.append(f"Name: {name}")
        
        # Add Skills
        if 'Skills' in cv_summary and cv_summary['Skills']:
            skills = cv_summary['Skills']
            if isinstance(skills, list):
                skills_text = " ".join([str(skill) for skill in skills])
            else:
                skills_text = str(skills)
            embedding_parts.append(f"Skills: {skills_text}")
        
        # Add Experience
        if 'Experience' in cv_summary and cv_summary['Experience']:
            experience = cv_summary['Experience']
            if isinstance(experience, list):
                exp_texts = []
                for exp in experience:
                    if isinstance(exp, dict):
                        exp_parts = []
                        if exp.get('Role'):
                            exp_parts.append(f"Role: {exp['Role']}")
                        if exp.get('Company'):
                            exp_parts.append(f"Company: {exp['Company']}")
                        if exp.get('Description'):
                            exp_parts.append(f"Description: {exp['Description']}")
                        if exp_parts:
                            exp_texts.append(" | ".join(exp_parts))
                    else:
                        exp_texts.append(str(exp))
                exp_text = " || ".join(exp_texts)
            else:
                exp_text = str(experience)
            embedding_parts.append(f"Experience: {exp_text}")
        
        # Add Education
        if 'Education' in cv_summary and cv_summary['Education']:
            education = cv_summary['Education']
            if isinstance(education, list):
                edu_texts = []
                for edu in education:
                    if isinstance(edu, dict):
                        edu_parts = []
                        if edu.get('Degree'):
                            edu_parts.append(f"Degree: {edu['Degree']}")
                        if edu.get('School'):
                            edu_parts.append(f"School: {edu['School']}")
                        if edu.get('Field'):
                            edu_parts.append(f"Field: {edu['Field']}")
                        if edu_parts:
                            edu_texts.append(" | ".join(edu_parts))
                    else:
                        edu_texts.append(str(edu))
                edu_text = " || ".join(edu_texts)
            else:
                edu_text = str(education)
            embedding_parts.append(f"Education: {edu_text}")
        
        # Combine all parts
        combined_text = " | ".join(embedding_parts)
        
        # Fallback to raw response if structured fields are empty
        if not combined_text.strip() and 'raw' in cv_summary:
            combined_text = str(cv_summary['raw'])[:1000]  # Limit raw text
        
        return combined_text if combined_text.strip() else "No structured information available"
    
    async def process_and_store_cv(self, user_id: int, cv_id: int, cv_summary: dict) -> bool:
        """
        Process CV summary and store its embedding in the database.
        
        Args:
            user_id: User ID who owns the CV
            cv_id: CV database ID
            cv_summary: Parsed CV summary JSON
            
        Returns:
            True if successfully processed and stored
        """
        try:
            # Create embedding text from CV summary
            embedding_text = self.create_embedding_text(cv_summary)
            
            if embedding_text and embedding_text != "No structured information available":
                # Generate embedding
                embedding = embed_model.get_embedding(embedding_text)
                
                # Store in database
                embedding_id = await DatabaseManager.save_cv_embedding(
                    cv_id=cv_id,
                    user_id=user_id,
                    embedding=embedding,
                    embedding_text=embedding_text
                )
                
                if embedding_id:
                    print(f"✓ Stored embedding for CV ID {cv_id}")
                    print(f"   Embedding text: {embedding_text[:100]}...")
                    return True
                else:
                    print(f"✗ Failed to store embedding for CV ID {cv_id}")
                    return False
            else:
                print(f"⚠ No usable content for CV ID {cv_id}")
                return False
                
        except Exception as e:
            print(f"✗ Error processing CV {cv_id}: {e}")
            return False
    
    async def search_user_cvs(self, user_id: int, query: str, top_k: int = 3) -> List[Dict]:
        """
        Search for similar CVs for a specific user using cosine similarity.
        
        Args:
            user_id: User ID to search within
            query: Text query to search for
            top_k: Number of top results to return
            
        Returns:
            List of CV info dictionaries with similarity scores
        """
        try:
            print(f"Searching CVs for user {user_id} with query: '{query}'")
            
            # Get query embedding
            query_embedding = embed_model.get_embedding(query)
            
            # Get all user embeddings from database
            user_embeddings = await DatabaseManager.get_user_embeddings(user_id)
            
            if not user_embeddings:
                print(f"No embeddings found for user {user_id}")
                return []
            
            print(f"Found {len(user_embeddings)} embeddings for user {user_id}")
            
            # Calculate similarities
            results = []
            for emb_data in user_embeddings:
                cv_embedding = emb_data['embedding']
                
                # Calculate cosine similarity
                similarity = cosine_similarity(
                    query_embedding.reshape(1, -1),
                    cv_embedding.reshape(1, -1)
                )[0][0]
                
                result = {
                    'cv_id': emb_data['cv_id'],
                    'filename': emb_data['filename'],
                    'candidate_name': emb_data['candidate_name'],
                    'similarity': float(similarity),
                    'embedding_text': emb_data['embedding_text']
                }
                results.append(result)
            
            # Sort by similarity (descending)
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Return top_k results
            top_results = results[:top_k]
            
            print(f"Top {len(top_results)} results:")
            for i, result in enumerate(top_results):
                print(f"{i+1}. {result['filename']} - {result['candidate_name']} (similarity: {result['similarity']:.4f})")
                print(f"   Preview: {result['embedding_text'][:100]}...")
            
            return top_results
            
        except Exception as e:
            print(f"✗ Error searching CVs: {e}")
            return []
    
    async def get_cv_full_summary(self, cv_id: int, user_id: int) -> Optional[Dict]:
        """
        Get the full CV summary for a given CV ID.
        
        Args:
            cv_id: CV database ID
            user_id: User ID for access control
            
        Returns:
            Complete CV summary dictionary
        """
        try:
            cv_data = await DatabaseManager.get_cv_by_id(cv_id, user_id)
            
            if cv_data and cv_data.get('summary_json'):
                return cv_data['summary_json']
            else:
                print(f"No summary found for CV ID {cv_id}")
                return None
                
        except Exception as e:
            print(f"✗ Error getting CV summary: {e}")
            return None
    
    async def rebuild_user_embeddings(self, user_id: int) -> bool:
        """
        Rebuild all embeddings for a user's CVs.
        Useful after CV processing changes or embedding model updates.
        
        Args:
            user_id: User ID to rebuild embeddings for
            
        Returns:
            True if successful
        """
        try:
            print(f"Rebuilding embeddings for user {user_id}")
            
            # Get all user CVs with summaries
            user_cvs = await DatabaseManager.get_user_cvs(user_id, limit=1000)
            
            rebuilt_count = 0
            for cv in user_cvs:
                cv_id = cv['id']
                
                # Get full CV data including summary
                cv_data = await DatabaseManager.get_cv_by_id(cv_id, user_id)
                
                if cv_data and cv_data.get('summary_json'):
                    # Delete existing embeddings for this CV
                    await DatabaseManager.delete_cv_embeddings(cv_id, user_id)
                    
                    # Process and store new embedding
                    success = await self.process_and_store_cv(
                        user_id, cv_id, cv_data['summary_json']
                    )
                    
                    if success:
                        rebuilt_count += 1
                        print(f"✓ Rebuilt embedding for {cv['filename']}")
                    else:
                        print(f"✗ Failed to rebuild embedding for {cv['filename']}")
                else:
                    print(f"⚠ No summary available for {cv['filename']}")
            
            print(f"✓ Rebuilt {rebuilt_count} embeddings for user {user_id}")
            return True
            
        except Exception as e:
            print(f"✗ Error rebuilding embeddings: {e}")
            return False
    
    async def get_user_embedding_stats(self, user_id: int) -> Dict:
        """
        Get embedding statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with embedding statistics
        """
        try:
            user_embeddings = await DatabaseManager.get_user_embeddings(user_id)
            
            if not user_embeddings:
                return {
                    'total_embeddings': 0,
                    'avg_embedding_text_length': 0,
                    'embedding_dimension': self.dimension
                }
            
            total_length = sum(len(emb['embedding_text']) for emb in user_embeddings)
            avg_length = total_length / len(user_embeddings)
            
            return {
                'total_embeddings': len(user_embeddings),
                'avg_embedding_text_length': round(avg_length, 2),
                'embedding_dimension': self.dimension,
                'sample_embeddings': [
                    {
                        'filename': emb['filename'],
                        'candidate_name': emb['candidate_name'],
                        'text_preview': emb['embedding_text'][:100] + "..."
                    }
                    for emb in user_embeddings[:3]  # Show first 3 as samples
                ]
            }
            
        except Exception as e:
            print(f"✗ Error getting embedding stats: {e}")
            return {'error': str(e)}


# Global vector store instance
_vector_store = PostgreSQLVectorStore()

# Convenience functions for backward compatibility
async def process_and_store_cv(user_id: int, cv_id: int, cv_summary: dict) -> bool:
    """Process and store CV embedding using global instance."""
    return await _vector_store.process_and_store_cv(user_id, cv_id, cv_summary)

async def search_user_cvs(user_id: int, query: str, top_k: int = 3) -> List[Dict]:
    """Search user's CVs using global instance."""
    return await _vector_store.search_user_cvs(user_id, query, top_k)

async def get_cv_full_summary(cv_id: int, user_id: int) -> Optional[Dict]:
    """Get full CV summary using global instance."""
    return await _vector_store.get_cv_full_summary(cv_id, user_id)

async def rebuild_user_embeddings(user_id: int) -> bool:
    """Rebuild user embeddings using global instance."""
    return await _vector_store.rebuild_user_embeddings(user_id)

async def get_user_embedding_stats(user_id: int) -> Dict:
    """Get user embedding statistics using global instance."""
    return await _vector_store.get_user_embedding_stats(user_id)