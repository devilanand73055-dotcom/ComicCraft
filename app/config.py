import os
from pathlib import Path
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    image_backend: str = Field(default="huggingface", validation_alias="IMAGE_BACKEND")
    image_model: str = Field(
        default="",
        validation_alias=AliasChoices("IMAGE_MODEL", "HF_IMAGE_MODEL"),
    )
    image_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("IMAGE_API_KEY", "HF_API_KEY"),
    )
    pollinations_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="POLLINATIONS_API_KEY",
    )
    
    # Path settings
    base_dir: Path = BASE_DIR
    templates_dir: Path = BASE_DIR / "templates"
    static_dir: Path = BASE_DIR / "static"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

def get_settings():
    return settings