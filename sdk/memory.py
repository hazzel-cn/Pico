from typing import List, Dict, Any
from loguru import logger

# Simple in-memory storage for now. 
# Could be extended to JSON files for persistence if needed later.
_history: Dict[str, List[Dict[str, str]]] = {}

def get_history(user_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """Retrieve the last N messages for a user."""
    return _history.get(str(user_id), [])[-limit:]

def add_message(user_id: str, role: str, content: str):
    """Add a message to the user's history."""
    uid = str(user_id)
    if uid not in _history:
        _history[uid] = []
    
    _history[uid].append({"role": role, "content": content})
    
    # Keep history bounded to avoid OOM or context limit issues
    if len(_history[uid]) > 50:
        _history[uid] = _history[uid][-50:]

def clear_history(user_id: str):
    """Clear the history for a specific user."""
    uid = str(user_id)
    if uid in _history:
        _history[uid] = []
        logger.info(f"Memory cleared for user {uid}")
