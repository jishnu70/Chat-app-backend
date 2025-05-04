from pydantic import BaseModel
from typing import Optional

class ChatSummary(BaseModel):
    chat_id: int
    title: str
    last_message: str
    is_group: bool

class UserCreate(BaseModel):
    uid: str
    email: str
    username: str
    public_key: str

class UserOut(BaseModel):
    id: int
    uid: str
    email: str
    username: str
    public_key: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True