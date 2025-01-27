from typing import Optional

from pydantic import BaseModel


class FunctionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class FunctionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
