import os
import sys
import json
import re
from typing import List, Optional, Dict
import faiss_store
import llama_inference


def extract_cv_count_from_query(user_query: str) -> int:
    """Extract number of CVs to retrieve based on query."""
    query_lower = user_query.lower()
    
    # Look for numbers in query
    if re.search(r'\b(\d+)', query_lower):
        match = re.search(r'\b(\d+)', query_lower)
        return min(int(match.group(1)), 10)
    
    # Smart defaults based on keywords
    if any(word in query_lower for word in ['all', 'every']):
        return 10
    elif any(word in query_lower for word in ['best', 'summary']):
        return 5
    elif any(word in query_lower for word in ['one', 'top', 'single', 'specific']):
        return 1
    
    return 3


def load_cv_summary(summary_file: str) -> Optional[Dict]:
    """Load CV summary from JSON file."""
    try:
        with open(f"data/summaries/{summary_file}", 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {summary_file}: {e}")
        return None


def format_cv_for_prompt(cv_summary: Dict, rank: int) -> str:
    """Format CV summary for the prompt."""
    lines = [f"=== CANDIDATE {rank} ==="]
    
    # Name
    if cv_summary.get('Name'):
        lines.append(f"Name: {cv_summary['Name']}")
    
    # Contact
    if cv_summary.get('Email'):
        lines.append(f"Email: {cv_summary['Email']}")
    if cv_summary.get('Phone'):
        lines.append(f"Phone: {cv_summary['Phone']}")
    
    # Education
    if cv_summary.get('Education'):
        lines.append("\nEducation:")
        for edu in cv_summary['Education'][:3]:  # Limit to 3 entries
            if isinstance(edu, dict):
                degree = edu.get('Degree', '')
                school = edu.get('School', '')
                if degree and school:
                    lines.append(f"  • {degree} - {school}")
                elif degree:
                    lines.append(f"  • {degree}")
                elif school:
                    lines.append(f"  • {school}")
            else:
                lines.append(f"  • {str(edu)}")
    
    # Experience
    if cv_summary.get('Experience'):
        lines.append("\nExperience:")
        for exp in cv_summary['Experience'][:4]:  # Limit to 4 entries
            if isinstance(exp, dict):
                company = exp.get('Company', '')
                role = exp.get('Role', '')
                if company and role:
                    lines.append(f"  • {role} at {company}")
                elif company:
                    lines.append(f"  • {company}")
                elif role:
                    lines.append(f"  • {role}")
            else:
                lines.append(f"  • {str(exp)}")
    
    # Skills
    if cv_summary.get('Skills'):
        skills = cv_summary['Skills']
        if isinstance(skills, list):
            skills_text = ", ".join(skills[:15])  # Limit skills
        else:
            skills_text = str(skills)
        lines.append(f"\nSkills: {skills_text}")
    
    # Languages
    if cv_summary.get('Languages'):
        languages = cv_summary['Languages']
        if isinstance(languages, list):
            lang_text = " | ".join(languages[:5])
        else:
            lang_text = str(languages)
        lines.append(f"Languages: {lang_text}")
    
    return "\n".join(lines) + "\n\n"


def build_prompt(user_query: str, cv_results: List[Dict]) -> str:
    """Build prompt for LLaMA with CV summaries."""
    prompt = f"""You are an AI assistant analyzing CVs to answer recruitment questions.

User Question: "{user_query}"

Here are the most relevant candidate profiles:

"""
    
    for i, result in enumerate(cv_results, 1):
        summary_file = result.get('summary_file', '')
        score = result.get('score', 0)
        
        cv_summary = load_cv_summary(summary_file)
        if cv_summary:
            prompt += format_cv_for_prompt(cv_summary, i)
            prompt += f"(Relevance Score: {score:.3f})\n\n"
    
    prompt += """
Instructions:
- Answer the user's question based on these CV profiles
- Be specific and use details from the CVs
- If asked for "best" candidates, rank and explain why
- Compare candidates when relevant
- Focus on matching skills and experience to the query
"""
    
    return prompt


def process_query(user_query: str, top_k: Optional[int] = None) -> str:
    """Process user query through RAG pipeline."""
    print(f"Processing query: '{user_query}'")
    print("-" * 50)
    
    # Determine number of CVs to retrieve
    if top_k is None:
        top_k = extract_cv_count_from_query(user_query)
        print(f"Auto-determined to retrieve top {top_k} CVs")
    
    # Search for relevant CVs
    print("🔍 Searching for relevant CVs...")
    cv_results = faiss_store.search(user_query, top_k)
    
    if not cv_results:
        return "Sorry, I couldn't find any relevant CVs. Please ensure the FAISS index is built."
    
    print(f"Found {len(cv_results)} relevant CVs:")
    for i, result in enumerate(cv_results, 1):
        summary_file = result.get('summary_file', 'Unknown')
        score = result.get('score', 0)
        print(f"  {i}. {summary_file} (Score: {score:.3f})")
    
    # Build prompt and get response
    print("🔨 Building prompt...")
    prompt = build_prompt(user_query, cv_results)
    print(f"Prompt ready ({len(prompt)} characters)")
    
    print("🤖 Getting LLaMA response...")
    response = llama_inference.run_llama(prompt)
    
    return response


def interactive_mode():
    """Run interactive query mode."""
    print("=" * 60)
    print("🎯 CV RAG System - Interactive Mode")
    print("=" * 60)
    print("Ask questions about CVs. Type 'quit' to exit.\n")
    print("Example queries:")
    print("• 'Give me our best mechanical engineers'")
    print("• 'Find top 3 Python developers'") 
    print("• 'Who knows machine learning?'")
    print("• 'Show me all software engineers'\n")
    
    # System checks
    if not faiss_store.load_index():
        print("❌ FAISS index not found! Please build it first.")
        return
    print("✅ FAISS index loaded")
    
    if not llama_inference.check_ollama_available():
        print("❌ Ollama not available!")
        return
    if not llama_inference.check_model_available():
        print("❌ LLaMA3 model not available!")
        return
    print("✅ LLaMA3 ready\n")
    
    while True:
        try:
            user_input = input("🤔 Your question: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            print()
            response = process_query(user_input)
            
            print("\n" + "=" * 60)
            print("🤖 Response:")
            print("=" * 60)
            print(response)
            print("\n" + "-" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


def main():
    """Main function."""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        response = process_query(query)
        print("\nResponse:")
        print(response)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()