from typing import List, Callable, Optional
from loguru import logger
import sdk.config as config

from .base import BaseAgent, ToolRequest
from .openai import OpenAIAgent
from .ollama import OllamaAgent
from .google import GeminiAgent

def get_agent(tools: List[Callable], model_name: Optional[str] = None, provider: Optional[str] = None) -> BaseAgent:
    """Factory to get the correct agent implementation. Uses config defaults."""
    
    # 1. Determine Provider
    provider = provider or config.DEFAULT_PROVIDER
    
    # 2. Map Provider to Agent & Default Model
    if provider == "openai":
        model = model_name or config.OPENAI_MODEL
        logger.info(f"Factory: Creating OpenAIAgent with {model}")
        return OpenAIAgent(model, tools)
        
    if provider == "google" or provider == "gemini":
        model = model_name or config.GOOGLE_MODEL
        logger.info(f"Factory: Creating GeminiAgent with {model}")
        return GeminiAgent(model, tools)
        
    if provider == "ollama":
        model = model_name or config.OLLAMA_MODEL
        logger.info(f"Factory: Creating OllamaAgent with {model}")
        return OllamaAgent(model, tools, api_base=config.OLLAMA_URL)

    # Fallback to auto-detect if someone passed model_name but no provider
    if model_name:
        if model_name.startswith("gpt") or model_name.startswith("o1"):
            return OpenAIAgent(model_name, tools)
        if model_name.startswith("gemini"):
            return GeminiAgent(model_name, tools)
        return OllamaAgent(model_name, tools, api_base=config.OLLAMA_URL)
        
    raise ValueError(f"Unknown provider: {provider}")
