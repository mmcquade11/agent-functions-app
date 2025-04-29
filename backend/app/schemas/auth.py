from pydantic import BaseModel
from typing import List

class TokenPayload(BaseModel):
    sub: str
    permissions: List[str] = []
