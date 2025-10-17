from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id")
    role: str  # 'user' or 'assistant'
    content: str
    reasoning: Optional[str] = None  # AI reasoning (if available)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_id: Optional[str] = None  # Celery task ID for tracking

    # Relationship
    conversation: Optional["Conversation"] = Relationship(back_populates="messages")


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    messages: List["Message"] = Relationship(back_populates="conversation", cascade_delete=True)


class StreamChunk(SQLModel, table=True):
    __tablename__ = "stream_chunks"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)  # Celery task ID
    message_id: Optional[int] = Field(default=None, foreign_key="messages.id")
    chunk_index: int  # Order of chunks
    chunk_type: str  # 'content', 'reasoning', 'done', or 'error'
    content: str  # Chunk content
    created_at: datetime = Field(default_factory=datetime.utcnow)
