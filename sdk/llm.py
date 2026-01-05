import httpx
import sdk.config as config
from loguru import logger

class LLMClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.OLLAMA_URL

    async def generate(self, prompt: str, model: str = "qwen2.5:7b") -> str:
        """
        Generate text using Ollama. (Currently unused/disabled in business logic)
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json=payload, timeout=60.0)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
            except Exception as e:
                logger.error(f"LLM Generation failed: {e}")
                return ""


# New Capability: Model Listing
import ollama

async def get_available_models() -> list[dict]:
    """
    Get list of available models with metadata.
    Returns: [{'provider': str, 'model': str, 'label': str}]
    """
    results = []
    
    # 1. Configured Defaults (High Priority)
    if config.OPENAI_API_KEY:
        results.append({
            "provider": "openai", 
            "model": config.OPENAI_MODEL, 
            "label": f"🧠 OpenAI ({config.OPENAI_MODEL})"
        })
    if config.GOOGLE_API_KEY:
        results.append({
            "provider": "google", 
            "model": config.GOOGLE_MODEL, 
            "label": f"✨ Gemini ({config.GOOGLE_MODEL})"
        })
    if config.OLLAMA_MODEL:
        results.append({
            "provider": "ollama", 
            "model": config.OLLAMA_MODEL, 
            "label": f"🤖 Ollama ({config.OLLAMA_MODEL})"
        })

    # 2. Other local Ollama models
    try:
        from ollama import AsyncClient
        client = AsyncClient(host=config.OLLAMA_URL)
        resp = await client.list()
        if 'models' in resp:
            for m in resp['models']:
                name = m['name']
                # Skip if it's already our default ollama model
                if name == config.OLLAMA_MODEL:
                    continue
                results.append({
                    "provider": "ollama",
                    "model": name,
                    "label": f"🏠 Local: {name}"
                })
    except Exception as e:
        logger.error(f"Failed to list additional Ollama models: {e}")
        
    return results
