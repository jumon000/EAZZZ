import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost/eazz_db"
    openai_api_key: str = "YOUR_OPENAI_API_KEY" # Make sure this is set
   
    autogen_planner_model: str = "gpt-4-turbo-preview" # Or your preferred planner model
    autogen_executor_model: str = "gpt-3.5-turbo"   # Or your preferred executor model
    autogen_max_consecutive_auto_reply: int = 5 # Safety limit
    autogen_timeout_seconds: int = 120 # Timeout for agent responses
    
    secret_key: str = "YOUR_VERY_SECRET_KEY"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8' 

settings = Settings()