from typing import List, Callable, Any, Optional
import ollama
from loguru import logger
from .base import BaseAgent, ToolRequest

class OllamaAgent(BaseAgent):
    """
    Lightweight agent using official Ollama SDK for local models.
    Supports interactive confirmation and direct output.
    """
    def __init__(self, model_name: str, tools: List[Callable], api_base: Optional[str] = None):
        super().__init__(model_name, tools)
        self.api_base = api_base
        self.client = ollama.AsyncClient(host=api_base)

    async def chat(self, user_id: str, message: str) -> Any:
        from sdk import memory
        memory.add_message(user_id, "user", message)
        
        history = memory.get_history(user_id)
        
        messages = [
            {"role": "system", "content": config.SYSTEM_PROMPT}
        ]
        messages.extend(history)
        
        logger.info(f"Ollama (context: {len(history)}) Request: {message}")
        try:
             # Use official Ollama SDK
             response = await self.client.chat(
                 model=self.model_name,
                 messages=messages,
                 tools=self.tool_schemas,
                 options={"temperature": 0.1}
             )
             
             msg = response['message']
             
             # Check for tool calls
             if msg.get('tool_calls'):
                 tool_call = msg['tool_calls'][0]
                 fname = tool_call['function']['name']
                 args = tool_call['function']['arguments']
                 logger.info(f"OllamaAgent Requesting Tool: {fname}({args})")
                 return ToolRequest(name=fname, args=args)
             
             # Final response
             content = msg.get('content')
             if not content:
                  return "I'm thinking... (Empty Response)"
             
             memory.add_message(user_id, "assistant", content)
             return content
             
        except Exception as e:
            logger.error(f"OllamaAgent Error: {e}")
            return f"Error: {e}"
