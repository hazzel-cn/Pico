import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# Calculate project root (assuming this file is in core/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

class Settings(BaseSettings):
    BARK_URL: str = ""
    OLLAMA_URL: str = "http://localhost:11434"
    TEMP_THRESHOLD: float = 80.0
    GAMMU_INBOX_PATH: str = "/var/spool/gammu/inbox"
    GAMMU_INBOX_PATH: str = "/var/spool/gammu/inbox"
    
    # Feature Flags
    # Feature Flags
    ENABLE_SMS_FORWARDER: bool = True
    ENABLE_SYSTEM_TEMP: bool = True
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_USERS: list[int] = [] # List of allowed user IDs
    
    # AI / LLM
    GOOGLE_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5.2"
    OPENAI_API_KEY: str | None = None # Default to Qwen


    model_config = SettingsConfigDict(env_file=ENV_FILE, env_ignore_empty=True)

settings = Settings()
