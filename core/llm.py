import httpx
from core.config import settings
from core.logger import logger

class LLMClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.OLLAMA_URL

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

llm = LLMClient()
