import inspect
import json
import uuid
from abc import ABC, abstractmethod
from typing import List, Callable, Any, Dict, Optional
from dataclasses import dataclass, field
from loguru import logger

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
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

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
