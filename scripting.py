import os
import json
import requests
from abc import ABC, abstractmethod
from openai import OpenAI

# --- Configuration (can be adjusted) ---
# ACTIVE_PROVIDER = "ollama"  #let user decide in streamlit

OLLAMA_MODEL = "llama3.1"
OPENAI_MODEL = "gpt-4o-mini"
GROQ_MODEL = "llama3-8b-8192"

# --- Creating the AI models classes and function to generate answers ---

# Abstract Base Class (All inheriting classes will impliment generate())
class ModelProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Sends a prompt to the LLM and returns the raw string response."""
        pass

#Ollama Implementation
class OllamaClient(ModelProvider):
    def __init__(self, model_name=OLLAMA_MODEL, base_url="http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/api/chat" #endpoint for chat-style models
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "format": "json"  # Enforces JSON mode
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()['message']['content']
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama Connection Error: {e}")

#OpenAI Implementation
class OpenAIClient(ModelProvider):
    def __init__(self, model_name=OPENAI_MODEL, api_key=None):
        if not api_key:
            raise ValueError("OpenAI API Key is required for GPT-4o-mini.")

        self.client = OpenAI(api_key=api_key) #give the user the opportunity to enter his key in streamlit
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}  # Enforces JSON mode
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API Error: {e}")


#_____________________________________________________________________________________________________________________________________#

SYSTEM_PROMPT = """
You are a scriptwriter for a tech podcast, about IBM Z mainframes and linuxONE. You must generate an informal conversation dialogue between two personas based on the provided Topic and Context.

**The Personas:**
1. **The Skeptic:** Casual, questioning, slightly cynical. Doesn't buy into hype. Uses simple and gen z language.
2. **The Expert:** Knowledgeable, patient, factual. Uses analogies to explain complex concepts.

**Output Requirements:**
- You must output VALID JSON only.
- The format must be a list of objects: [{"speaker": "Skeptic", "text": "..."}, {"speaker": "Expert", "text": "..."}]
- Do not include any markdown formatting (like ```json). Just the raw JSON.
- Keep the dialogue engaging and approximately 12-16 exchanges long.
-Use and keep question marks when needed.
-Hard limit per sentence: max 1 comma and max 1 period
-Before returning JSON, scan every text periods except question marks.
"""

def get_provider(provider_name, api_key=None, ollama_url=None) -> ModelProvider:
    provider_name = provider_name.lower()
    
    if provider_name == "openai":
        return OpenAIClient(api_key=api_key, model_name=OPENAI_MODEL)
    
    elif provider_name == "groq":
        # Groq uses the OpenAI client but with a specific URL
        return OpenAIClient(
            api_key= api_key, 
            base_url="[https://api.groq.com/openai/v1](https://api.groq.com/openai/v1)",
            model_name=GROQ_MODEL
        )
        
    elif provider_name == "ollama":
        url = ollama_url if ollama_url else "http://localhost:11434"
        return OllamaClient(base_url=url)
        
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

def validate_json(raw_response):
    """
    Attempts to parse the JSON. Returns the parsed list if successful.
    Raises ValueError if parsing fails.
    """
    try:
        # cleanup potential markdown wrappers common in LLMs
        clean_text = raw_response.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        
        data = json.loads(clean_text)
        
        # Simple schema validation
        if not isinstance(data, list):
            # Sometimes LLMs wrap the list in a dict key like {"dialogue": [...]}
            if isinstance(data, dict) and len(data.keys()) == 1:
                key = list(data.keys())[0]
                if isinstance(data[key], list):
                    return data[key]
            raise ValueError("Root element must be a list of dialogue objects.")
            
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON Syntax: {e}")

# --- generating a script (with a retry system implimented) ---

def generate_script(topic, context, provider="openai", api_key=None, ollama_url=None, max_retries=3):
    try:
        client = get_provider(provider, api_key, ollama_url)
    except Exception as e:
        print(f"Provider Initialization Error: {e}")
        return None

    # Initial Prompt
    prompt = f"Topic: {topic}\nContext Data: {context}\n\nGenerate the dialogue JSON:"
    current_prompt = prompt
    
    for attempt in range(max_retries):
        print("attempting to generate script")
        # Call the LLM

        
        try:
            raw_response = client.generate(SYSTEM_PROMPT, current_prompt)
            script_json = validate_json(raw_response)
            return script_json 
            
        except ValueError as e:
            print(f"JSON Error on attempt {attempt + 1}: {e}")
            
            # RE-PROMPT (We feed the error back to the LLM so it can fix itself.)
            error_instruction = (
                f"\n\nERROR: Your previous output was invalid JSON. \n"
                f"Error details: {str(e)}\n"
                f"Please regenerate the ENTIRE JSON response correctly."
            )
            # Append the error to the prompt for the next loop (simulating conversation history)
            # In a real chat API we would append messages, but appending to prompt works for single-turn correction.
            current_prompt += error_instruction
        except Exception as e:
            print(f"API Error: {e}")
            return None

    print("Failed to generate valid JSON after multiple attempts.")
    return None


if __name__ == "__main__":
    # Example Usage
    sample_topic = "IBM Z mainframes and LinuxOne"
    sample_context = "IBM Z mainframes have 0 down time"
    
    script = generate_script(sample_topic, sample_context)
    
    if script:
        print("\n--- Generated Script ---")
        print(json.dumps(script, indent=2))
    else:
        print("failed")