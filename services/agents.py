import asyncio
import inspect
import json
import traceback
from abc import ABC, abstractmethod
from typing import List, Callable, Any, Dict, Optional
from dataclasses import dataclass

import openai
from core.config import settings
from core.logger import logger
import ollama

# --- Tools Schema Helper ---
def get_function_schema(func: Callable) -> dict:
    """Generate OpenAI-compatible tool schema from a function."""
    doc = func.__doc__ or ""
    sig = inspect.signature(func)
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    for name, param in sig.parameters.items():
        param_type = "string" # Default
        if param.annotation == int:
            param_type = "integer"
        elif param.annotation == float:
            param_type = "number"
        elif param.annotation == bool:
            param_type = "boolean"
            
        parameters["properties"][name] = {
            "type": param_type,
            "description": f"Parameter {name}" # Simplified
        }
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(name)
            
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc.strip(),
            "parameters": parameters
        }
    }

@dataclass
class ToolRequest:
    name: str
    args: dict

class BaseAgent(ABC):
    def __init__(self, model_name: str, tools: List[Callable]):
        self.model_name = model_name
        self.tools = tools
        self.tool_map = {f.__name__: f for f in tools}
        self.tool_schemas = [get_function_schema(f) for f in tools]

    @abstractmethod
    async def chat(self, user_id: str, message: str) -> str | ToolRequest:
        """Process a user message and return the response or a tool request."""
        pass

    async def execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool directly and return the raw output."""
        if name in self.tool_map:
            logger.info(f"Agent Executing Direct: {name}({args})")
            try:
                result = await self.tool_map[name](**args)
                return str(result)
            except Exception as e:
                return f"Error: {e}"
        return f"Error: Tool {name} not found."

class SlimAgent(BaseAgent):
    """
    Lightweight agent using official Ollama SDK for local models.
    Supports interactive confirmation and direct output.
    """
    def __init__(self, model_name: str, tools: List[Callable], api_base: Optional[str] = None):
        super().__init__(model_name, tools)
        self.api_base = api_base
        self.client = ollama.AsyncClient(host=api_base)

    async def chat(self, user_id: str, message: str) -> Any:
        # Stateless for local
        messages = [
            {"role": "system", "content": "You are Pico, a home assistant. Be concise. Use tools available."},
            {"role": "user", "content": message}
        ]
        
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
                 logger.info(f"SlimAgent Requesting Tool: {fname}({args})")
                 return ToolRequest(name=fname, args=args)
             
             # Final response
             content = msg.get('content')
             if not content:
                  return "I'm thinking... (Empty Response)"
             return content
             
        except Exception as e:
            logger.error(f"SlimAgent Error: {e}")
            return f"Error: {e}"

class OpenAIAgent(BaseAgent):
    """
    Stateless agent using official OpenAI SDK.
    """
    def __init__(self, model_name: str, tools: List[Callable]):
        super().__init__(model_name, tools)
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat(self, user_id: str, message: str) -> Any:
        messages = [
            {"role": "system", "content": "You are Pico, a home assistant. Be concise. Use tools available."},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tool_schemas if self.tool_schemas else None,
                tool_choice="auto" if self.tool_schemas else None
            )
            
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
            return content

        except Exception as e:
            logger.error(f"OpenAIAgent Error: {e}")
            return f"Error: {e}"

def get_agent(model_name: str, tools: List[Callable]) -> BaseAgent:
    """Factory to get the correct agent implementation."""
    if model_name.startswith("gpt") or model_name.startswith("o1"):
        logger.info(f"Factory: Creating OpenAIAgent for {model_name}")
        return OpenAIAgent(model_name, tools)
        logger.info(f"Factory: Creating SlimAgent for {model_name}")
        return SlimAgent(model_name, tools, api_base=settings.OLLAMA_URL)
