from pydantic import BaseModel
from typing import Optional

class PromptRequest(BaseModel):
    story_prompt: str
    character_name: str
    setting: str
    tone: str
    art_style: str

class ImageTestRequest(BaseModel):
    prompt: str