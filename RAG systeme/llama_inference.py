import requests
import json
import subprocess
from typing import Optional, Dict, Any,List
import subprocess
import requests
import time


class OllamaClient:
    """Fast Ollama client using REST API instead of subprocess."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
    
    def is_available(self) -> bool:
        """Check if Ollama server is running and responsive."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
        
    def start_server(self):
        """Try to start Ollama server if it's not running."""
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Ollama server started. Waiting for it to be ready...")
            time.sleep(3)  # Give the server a few seconds to start
        except Exception as e:
            print(f"Failed to start Ollama server: {e}")
    
    def get_available_models(self) -> list:
        """Get list of available models."""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except requests.RequestException:
            return []
    
    def check_model_available(self, model_name: str) -> bool:
        """Check if specific model is available."""
        models = self.get_available_models()
        return any(model_name in model for model in models)
    
    def generate(self, prompt: str, model: str = 'llama3', **options) -> str:
        """Generate response using Ollama API."""
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": options
            }
            
            response = requests.post(
                f"{self.api_url}/generate", 
                json=payload,
                timeout=420  
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                return f"Error: HTTP {response.status_code} - {response.text}"
                
        except requests.Timeout:
            return "Error: Request timed out (5 minutes)"
        except requests.RequestException as e:
            return f"Error: Network request failed - {str(e)}"
        except json.JSONDecodeError:
            return "Error: Invalid JSON response from Ollama"


# Global client instance
_ollama_client = OllamaClient()

def start_server():
    """Try to start Ollama server if it's not running."""
    if _ollama_client.is_available():
        print("Ollama server is already running.")
    else:
        print("Starting Ollama server...")
        _ollama_client.start_server()
    
def check_ollama_available() -> bool:
    """Check if Ollama is available and responsive."""
    return _ollama_client.is_available()


def check_model_available(model_name: str = 'llama3') -> bool:
    """Check if a specific model is available."""
    return _ollama_client.check_model_available(model_name)


def get_available_models() -> list:
    """Get list of available models."""
    return _ollama_client.get_available_models()


def run_llama(prompt: str, model: str = 'llama3.2:3b', max_tokens: int = 600, 
              temperature: float = 0.7, **kwargs) -> str:
    """
    Fast LLaMA inference using REST API.
    
    Args:
        prompt: The prompt to send to the model
        model: Model name (default: 'llama3')  
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature (0.0-1.0)
        **kwargs: Additional options for Ollama
        
    Returns:
        Model response as string, or error message if failed
    """
    # Check if Ollama is available
    if not check_ollama_available():
        return "Error: Ollama server is not running. Please start Ollama first."
    
    # Check if model is available
    if not check_model_available(model):
        available_models = get_available_models()
        return f"Error: Model '{model}' not found. Available models: {available_models}"
    
    # Prepare options
    options = {
        'num_predict': max_tokens,
        'temperature': temperature,
        **kwargs
    }
    
    print(f"Running LLaMA inference with model: {model}")
    response = _ollama_client.generate(prompt, model, **options)
    
    if not response.startswith("Error:"):
        print("✓ LLaMA inference completed")
    
    return response


def run_llama_fast(prompt: str, model: str = 'llama3.2:3b', max_tokens: int = 1000) -> str:
    """
    Optimized function for fast CV summarization tasks.
    
    Args:
        prompt: The prompt to send to the model
        model: Model name (default: 'llama3')
        max_tokens: Maximum tokens (reduced for summaries)
        
    Returns:
        Model response as string, or error message if failed
    """
    return run_llama(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.1,  # Low temperature for consistent structured output
        top_p=0.9,
        repeat_penalty=1.1,
        format="json"
    )
    

def run_llama_with_history(conversation_history: list, model_name: str = "llama3.2:3b") -> str:
    """
    Run LLaMA with conversation history (simplified version).
    """
    # Convert history to a simple prompt
    if not conversation_history:
        return "No conversation history available."
    
    # Get the last user message
    last_user_msg = None
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
    
    if not last_user_msg:
        return "No user message found in history."
    
    # Use the simple run_llama function
    return run_llama(last_user_msg, model_name)



def test_llama_connection():
    """Test function to verify LLaMA connection with API."""
    print("Testing LLaMA connection via REST API...")
    
    if not check_ollama_available():
        print("✗ Ollama server is not running")
        print("Please start Ollama: ollama serve")
        return False
    
    print("✓ Ollama server is running")
    
    available_models = get_available_models()
    print(f"Available models: {available_models}")
    
    if not available_models:
        print("✗ No models found")
        print("Please install a model: ollama pull llama3")
        return False
    
    # Test with first available model
    test_model = 'llama3' if check_model_available('llama3') else available_models[0]
    print(f"✓ Testing with model: {test_model}")
    
    # Test with simple prompt
    test_prompt = "Say 'Hello from LLaMA!' and nothing else."
    print("Testing with simple prompt...")
    response = run_llama_fast(test_prompt, model=test_model, max_tokens=50)
    
    if response.startswith("Error:"):
        print(f"✗ Test failed: {response}")
        return False
    
    print(f"✓ Test successful! Response: {response[:100]}...")
    return True