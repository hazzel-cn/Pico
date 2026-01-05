from typing import List, Callable, Any, Optional
import google.generativeai as genai
from loguru import logger
import sdk.config as config
from .base import BaseAgent, ToolRequest

class GeminiAgent(BaseAgent):
    """
    Agent using Google's Generative AI SDK (Gemini).
    """
    def __init__(self, model_name: str, tools: List[Callable], api_key: Optional[str] = None):
        super().__init__(model_name, tools)
        self.api_key = api_key or config.GOOGLE_API_KEY
        if not self.api_key:
             raise ValueError("API Key required for Google models (check config.GOOGLE_API_KEY)")
        
        genai.configure(api_key=self.api_key)
        # Gemini accepts functions directly in 'tools'
        self.model = genai.GenerativeModel(
            model_name=model_name, 
            tools=tools,
            system_instruction=config.SYSTEM_PROMPT
        )

    async def chat(self, user_id: str, message: str) -> str | ToolRequest:
        from sdk import memory
        
        # Add user message to memory
        memory.add_message(user_id, "user", message)
        
        # Build context from history
        history = memory.get_history(user_id)
        
        # Start chat session with history
        chat = self.model.start_chat(history=[
            {"role": m["role"] if m["role"] != "assistant" else "model", "parts": [m["content"]]} 
            for m in history[:-1] # All except the current message which is passed to send_message
        ])
        
        logger.info(f"Gemini (context: {len(history)}) Request: {message}")
        
        try:
            response = await chat.send_message_async(message)
            
            # Check for function calls in any part
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    # Add Tool Call intent to memory so context is preserved
                    memory.add_message(user_id, "assistant", f"[Tool Call: {fc.name}({dict(fc.args)})]")
                    return ToolRequest(name=fc.name, args=dict(fc.args))

            # No function call, get text response
            text_response = response.text
            # Add AI response to memory
            memory.add_message(user_id, "assistant", text_response)
            return text_response
            
        except Exception as e:
            logger.error(f"GoogleAgent Error: {e}")
            return f"Error: {e}"
