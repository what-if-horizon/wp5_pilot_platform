import os
from google import genai
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class GeminiClient:
    """Client for interacting with Google Gemini API."""
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize Gemini client.
        
        Args:
            model_name: Gemini model to use (default: gemini-2.0-flash-exp for speed/cost)
        """
        self.model_name = model_name
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    def generate_response(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """
        Generate a response from Gemini.
        
        Args:
            prompt: The prompt to send to the model
            max_retries: Number of retries on failure (default: 1)
        
        Returns:
            Generated text response, or None if all attempts fail
        """
        attempts = 0
        last_error = None
        
        while attempts <= max_retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return response.text
            
            except Exception as e:
                last_error = str(e)
                attempts += 1
                
                if attempts > max_retries:
                    # Log the failure and return None
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None
        
        return None


# Global instance for easy import
gemini_client = GeminiClient()