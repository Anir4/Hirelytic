import os
import sys
import json
import re
from typing import List, Optional, Dict
import asyncio
from database import DatabaseManager
import faiss_store as vector_store  # Now the PostgreSQL-based vector store
import llama_inference


class HRAssistant:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.conversation_history = []
        self.max_history_length = 10  # Keep last 10 exchanges
        # Load recent conversation history from database
        asyncio.create_task(self._load_conversation_history())
        
    async def initialize(self):
        """Initialize assistant with conversation history from database."""
        await self._load_conversation_history()
    
    async def _load_conversation_history(self):
        """Load recent conversation history from database."""
        try:
            # Get recent chats from database (limit to max_history_length exchanges)
            recent_chats = await DatabaseManager.get_user_chats(self.user_id, limit=self.max_history_length)
            
            # Convert database chats to conversation history format
            self.conversation_history = []
            for chat in reversed(recent_chats):  # Reverse to get chronological order
                self.conversation_history.append({
                    "role": "user",
                    "content": chat['query']
                })
                self.conversation_history.append({
                    "role": "assistant", 
                    "content": chat['response_text']
                })
            
            # Keep only recent history to avoid token limits
            if len(self.conversation_history) > self.max_history_length * 2:
                self.conversation_history = self.conversation_history[-self.max_history_length * 2:]
                
            print(f"✓ Loaded {len(self.conversation_history)//2} conversation exchanges from database")
            
        except Exception as e:
            print(f"Warning: Could not load conversation history: {e}")
            self.conversation_history = []
        
    async def add_to_history(self, user_message: str, assistant_response: str, cv_results: Optional[Dict] = None):
        """Add exchange to conversation history and save to database."""
        # Add to in-memory history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        self.conversation_history.append({
            "role": "assistant", 
            "content": assistant_response
        })
        
        # Keep only recent history to avoid token limits
        if len(self.conversation_history) > self.max_history_length * 2:
            self.conversation_history = self.conversation_history[-self.max_history_length * 2:]
        
        # Save to database
        try:
            from database import ChatCreate
            query_type = "cv_search" if self.is_cv_search_query(user_message) else "general_chat"
            chat_data = ChatCreate(
                query=user_message,
                query_type=query_type,
                response_text=assistant_response,
                cv_results=cv_results if query_type == "cv_search" else None

            )
            await DatabaseManager.save_chat(self.user_id, chat_data)
        except Exception as e:
            print(f"Warning: Could not save chat to database: {e}")
    
    def build_history_context(self) -> str:
        """Build context from conversation history."""
        if not self.conversation_history:
            return ""
        
        context = "Previous conversation:\n"
        for msg in self.conversation_history[-6:]:  # Last 3 exchanges
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {msg['content'][:100]}...\n"  # Truncate long messages
        
        return context + "\n"
        
    def is_cv_search_query(self, query: str) -> bool:
        """Simple keyword-based intent detection."""
        keywords = [
            'find', 'show', 'get', 'best', 'top', 'candidates', 'profiles', 
            'cvs', 'resumes', 'engineers', 'developers', 'skills', 'experience',
            'python', 'java', 'mechanical', 'electrical', 'software', 'who'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in keywords)
    
    def needs_context(self, query: str) -> bool:
        """Check if query needs conversation context."""
        context_indicators = [
            'that', 'this', 'them', 'those', 'previous', 'earlier', 'before',
            'also', 'too', 'more', 'another', 'what about', 'how about'
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in context_indicators)
    
    def extract_cv_count(self, query: str) -> int:
        """Extract number of CVs to retrieve."""
        query_lower = query.lower()
        
        # Look for explicit numbers
        if match := re.search(r'\b(\d+)\b', query_lower):
            return min(int(match.group(1)), 10)
        
        # Keyword-based detection
        if any(word in query_lower for word in ['all', 'every']):
            return 5
        elif any(word in query_lower for word in ['one', 'single','best', 'top']):
            return 3
        
        return 4
    
    async def load_cv_summary(self, cv_id: int) -> Optional[Dict]:
        """Load CV summary from database."""
        try:
            return await vector_store.get_cv_full_summary(cv_id, self.user_id)
        except Exception as e:
            print(f"Error loading CV {cv_id}: {e}")
            return None
    
    def format_cv_summary(self, cv_summary: Dict, rank: int) -> str:
        """Format CV for prompt."""
        lines = [f"CANDIDATE {rank}:"]
        
        if cv_summary.get('Name'):
            lines.append(f"Name: {cv_summary['Name']}")
        
        # Education - simplified
        if cv_summary.get('Education'):
            edu_list = []
            for edu in cv_summary['Education'][:2]:
                if isinstance(edu, dict):
                    degree = edu.get('Degree', '')
                    school = edu.get('School', '')
                    if degree:
                        edu_list.append(degree)
                    elif school:
                        edu_list.append(school)
            if edu_list:
                lines.append(f"Education: {' | '.join(edu_list)}")
        
        # Experience - simplified  
        if cv_summary.get('Experience'):
            exp_list = []
            for exp in cv_summary['Experience'][:2]:
                if isinstance(exp, dict):
                    company = exp.get('Company', '')
                    role = exp.get('Role', '')
                    if role and company:
                        exp_list.append(f"{role} at {company}")
                    elif role:
                        exp_list.append(role)
                    elif company:
                        exp_list.append(company)
            if exp_list:
                lines.append(f"Experience: {' | '.join(exp_list)}")
        
        # Skills
        if cv_summary.get('Skills'):
            skills = cv_summary['Skills']
            if isinstance(skills, list):
                skills_text = ', '.join(skills[:10])
                lines.append(f"Skills: {skills_text}")
        
        return '\n'.join(lines) + '\n'
    
    async def build_search_prompt(self, user_query: str, cv_results: List[Dict]) -> str:
        """Build prompt for CV search queries with history context."""
        prompt = ""
        
        # Add conversation context if needed
        if self.needs_context(user_query):
            prompt += self.build_history_context()
        
        prompt += f"""You are an HR assistant. Answer this question: {user_query}
Only use relevant candidate data. Ignore irrelevant information.

CANDIDATES:
"""

        # Add candidate data
        for i, result in enumerate(cv_results, 1):
            cv_id = result.get('cv_id')
            cv_summary = await self.load_cv_summary(cv_id) if cv_id else None
            if cv_summary:
                prompt += self.format_cv_summary(cv_summary, i)

        prompt += "\nProvide direct, focused short answer only."
        return prompt
    
    def build_chat_prompt(self, user_query: str) -> str:
        """Build prompt for general chat with history."""
        prompt = ""
        
        # Always include some context for chat
        if self.conversation_history:
            prompt += self.build_history_context()
        
        prompt += f"You are a helpful HR assistant. User said: '{user_query}'. Give a brief, friendly response."
        return prompt
    
    async def handle_cv_search(self, user_query: str) -> str:
        """Handle CV search queries."""
        print("🔍 Searching CVs...")
        
        top_k = self.extract_cv_count(user_query)
        cv_results = await vector_store.search_user_cvs(self.user_id, user_query, top_k)
        
        if not cv_results:
            return "I couldn't find any relevant CVs for your query."
        
        print(f"Found {len(cv_results)} relevant profiles")
        
        # Build prompt and get response
        prompt = await self.build_search_prompt(user_query, cv_results)
        
        try:
            response = llama_inference.run_llama(prompt)
            if not response or response.strip() == "":
                return "I found the profiles but couldn't generate a response. Please try rephrasing your query."
            return response , cv_results
        except Exception as e:
            print(f"Error getting LLaMA response: {e}")
            return "Sorry, I encountered an error processing your request."
    
    def handle_chat(self, user_query: str) -> str:
        """Handle general chat with history."""
        # Check for simple responses first
        simple_responses = {
            'hi': "Hello! I'm your HR assistant. I can help you find candidates and answer questions about CVs. What would you like to know?",
            'hello': "Hi there! How can I help you with candidate profiles today?",
            'help': "I can help you find candidates by searching through CVs. Try asking things like 'find Python developers' or 'show me mechanical engineers'.",
            'thanks': "You're welcome! Feel free to ask about any candidates or profiles.",
            'thank you': "You're welcome! Feel free to ask about any candidates or profiles."
        }
        
        query_lower = user_query.lower().strip()
        
        # Check for simple responses first
        for key, response in simple_responses.items():
            if key in query_lower:
                return response
        
        # For other chat, use LLaMA with history context
        prompt = self.build_chat_prompt(user_query)
        
        try:
            response = llama_inference.run_llama(prompt, max_tokens=150, temperature=0.8)
            if not response or response.strip() == "":
                return "I'm here to help with HR and candidate questions. What would you like to know?"
            return response
        except Exception as e:
            print(f"Chat error: {e}")
            return "I'm here to help! Try asking me about candidates or CVs."
    
    async def process_query(self, user_query: str) -> str:
        """Main query processing with history management."""
        if not user_query.strip():
            return "Please ask me something!"
        
        # Process query
        if self.is_cv_search_query(user_query):
            response, cv_results = await self.handle_cv_search(user_query)
            await self.add_to_history(user_query, response, cv_results)
        else:
            response = self.handle_chat(user_query)
            await self.add_to_history(user_query, response, None)

        
        return response
    
    async def get_user_stats(self) -> Dict:
        """Get user statistics from database."""
        try:
            return await DatabaseManager.get_user_stats(self.user_id)
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {
                'total_cvs': 0, 'processed_cvs': 0, 
                'total_embeddings': 0, 'total_chats': 0
            }


async def interactive_mode():
    """Run interactive mode with history (for testing)."""
    print("=" * 50)
    print("🤖 HR Assistant with Chat History")
    print("=" * 50)
    print("I can help you find candidates! Type 'exit' to quit.\n")
    
    # For interactive mode, use a test user ID
    user_id = int(input("Enter your user ID: ").strip())
    
    assistant = HRAssistant(user_id)
    await assistant.initialize()  # Load conversation history
    
    print("✅ System ready!\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye!")
                break
                
            if not user_input:
                continue
            
            print("Assistant:", end=" ")
            response = await assistant.process_query(user_input)
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()


async def main():
    """Main function."""
    if len(sys.argv) > 2:
        user_id = int(sys.argv[1])
        query = " ".join(sys.argv[2:])
        assistant = HRAssistant(user_id)
        await assistant.initialize()  # Load conversation history
        response = await assistant.process_query(query)
        print(response)
    else:
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())