from typing import List
from pydantic import BaseModel, Field

class HashCheckIn(BaseModel):
    sha1: str = Field(..., description="Full SHA-1 hex (40 chars)")

class HashCheckOut(BaseModel):
    breached: bool
    count: int

class PasswordCheckIn(BaseModel):
    password: str

class SuffixItem(BaseModel):
    suffix: str   # hex string (40 - PREFIX_LEN chars)
    count: int

class RangeResponse(BaseModel):
    prefix: str                 # PREFIX_LEN hex chars
    suffixes: List[SuffixItem]  # list of {suffix, count}
