from pathlib import Path
from pydantic import Field, MongoDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    """
    Validates and structures all external API keys, tokens, and database connections.
    Pydantic automatically checks system environment variables first, falling back 
    to the local .env file if running in a developer space.
    """
    # 1. Core Discord Authentication
    discord_bot_token: str = Field(..., alias="DISCORD_BOT_TOKEN")
    
    # 2. Google Gemini Machine Learning Authentication
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    
    # 3. MongoDB Configuration
    # Using 'MongoDsn' forces Pydantic to validate that the connection string is well-formed
    mongo_uri: MongoDsn = Field(..., alias="MONGO_URI")

    # 4. Define configuration loading parameters
    model_config = SettingsConfigDict(
        # Looks for .env file at the workspace root directory relative to where main.py runs
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        # If an extra variable exists in the .env file that isn't typed above, ignore it safely
        extra="ignore",
        # Ensures case-insensitivity so DISCORD_BOT_TOKEN maps to discord_bot_token automatically
        case_sensitive=False
    )

# Instantiate a single global instance of our verified app configurations
settings = AppSettings()
