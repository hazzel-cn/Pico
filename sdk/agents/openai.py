import json
from typing import List, Callable, Any, Optional
import openai
from loguru import logger
import sdk.config as config
from .base import BaseAgent, ToolRequest

class OpenAIAgent(BaseAgent):
    """
    Stateless agent using official OpenAI SDK.
    """
    def __init__(self, model_name: str, tools: List[Callable], api_key: Optional[str] = None):
        super().__init__(model_name, tools)
        self.client = openai.AsyncOpenAI(api_key=api_key or config.OPENAI_API_KEY)

    async def chat(self, user_id: str, message: str) -> Any:
        from sdk import memory
        memory.add_message(user_id, "user", message)
        
        history = memory.get_history(user_id)
        
        messages = [
            {"role": "system", "content": config.SYSTEM_PROMPT}
        ]
        messages.extend(history)
        
        logger.info(f"OpenAI (context: {len(history)}) Request: {message}")
        try:
            # Prepare call arguments
            kwargs = {
                "model": self.model_name,
                "messages": messages,
                "tools": self.tool_schemas if self.tool_schemas else None,
                "tool_choice": "auto" if self.tool_schemas else None
            }
            
            # Add reasoning_effort for supported models (gpt-5 or o1)
            if "gpt-5" in self.model_name or "o1" in self.model_name:
                kwargs["reasoning_effort"] = config.OPENAI_REASONING_EFFORT

            response = await self.client.chat.completions.create(**kwargs)
            
            choice = response.choices[0]
            msg = choice.message
            
            # Check for tool calls
            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                fname = tool_call.function.name
                # Parse arguments (they are JSON strings)
                if tool_call.function.arguments:
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except:
                        args = {}
                else:
                    args = {}
                    
                logger.info(f"OpenAIAgent Requesting Tool: {fname}({args})")
                return ToolRequest(name=fname, args=args)
            
            content = msg.content
            if not content:
                 return "I'm thinking... (Empty Response)"
            
            memory.add_message(user_id, "assistant", content)
            return content

        except Exception as e:
            logger.error(f"OpenAIAgent Error: {e}")
            return f"Error: {e}"
