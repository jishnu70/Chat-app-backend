from pydantic import BaseModel

class ChatSummary(BaseModel):
    chat_id: int
    title: str
    last_message: str
    is_group: bool