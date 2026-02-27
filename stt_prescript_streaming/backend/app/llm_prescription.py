from typing import Any, Dict
from pydantic import BaseModel, Field

class RxRequest(BaseModel):
    text: str = Field(..., description="Dictated clinical note / transcript text")

class RxResponse(BaseModel):
    prescription: Dict[str, Any]
    markdown: str