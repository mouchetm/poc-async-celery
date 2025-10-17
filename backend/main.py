from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, select
from openai import AsyncOpenAI
import os
from typing import AsyncGenerator
import json
import logging
import asyncio
from datetime import datetime

from database import engine, get_session
from models import Conversation as ConversationModel, Message as MessageModel, StreamChunk
from schemas import ConversationPublic, ConversationCreate, MessageCreate
from dotenv import load_dotenv
from tasks import process_openai_stream

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("chat_api")

app = FastAPI(title="Chat API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.on_event("startup")
def on_startup():
    """Create database tables on startup"""
    logger.info("=" * 80)
    logger.info("Starting Chat API server")
    logger.info("=" * 80)
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")


@app.get("/")
def read_root():
    return {"message": "Chat API is running"}


@app.post("/conversations", response_model=ConversationPublic)
def create_conversation(
    conversation: ConversationCreate,
    session: Session = Depends(get_session)
):
    """Create a new conversation"""
    logger.info(f"Creating new conversation: '{conversation.title or 'New Conversation'}'")
    db_conversation = ConversationModel(
        title=conversation.title or "New Conversation"
    )
    session.add(db_conversation)
    session.commit()
    session.refresh(db_conversation)
    logger.info(f"✓ Conversation created: ID={db_conversation.id}, title='{db_conversation.title}'")
    return db_conversation


@app.get("/conversations/{conversation_id}", response_model=ConversationPublic)
def get_conversation(conversation_id: int, session: Session = Depends(get_session)):
    """Get a conversation by ID"""
    logger.info(f"Fetching conversation: ID={conversation_id}")
    conversation = session.get(ConversationModel, conversation_id)
    if not conversation:
        logger.warning(f"✗ Conversation not found: ID={conversation_id}")
        raise HTTPException(status_code=404, detail="Conversation not found")
    logger.info(f"✓ Conversation found: ID={conversation_id}, title='{conversation.title}'")
    return conversation


@app.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    message: MessageCreate,
    session: Session = Depends(get_session)
):
    """
    Send a message to a conversation and trigger AI processing via Celery.
    Returns immediately with task_id and message_id for streaming.
    """
    request_start = datetime.now()
    logger.info(f"")
    logger.info(f"{'='*80}")
    logger.info(f"📨 NEW MESSAGE REQUEST | Conversation ID: {conversation_id}")
    logger.info(f"Message preview: {message.content[:100]}{'...' if len(message.content) > 100 else ''}")
    logger.info(f"{'='*80}")
    
    # Verify conversation exists
    conversation = session.get(ConversationModel, conversation_id)
    if not conversation:
        logger.error(f"✗ Conversation not found: ID={conversation_id}")
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.info(f"[Conv {conversation_id}] Conversation found: '{conversation.title}'")

    # Save user message
    user_message = MessageModel(
        conversation_id=conversation_id,
        role="user",
        content=message.content
    )
    session.add(user_message)
    session.commit()
    session.refresh(user_message)
    logger.info(f"[Conv {conversation_id}] User message saved to database (ID: {user_message.id})")

    # Create placeholder assistant message
    assistant_message = MessageModel(
        conversation_id=conversation_id,
        role="assistant",
        content="",  # Will be populated by Celery task
        reasoning=None
    )
    session.add(assistant_message)
    session.commit()
    session.refresh(assistant_message)
    logger.info(f"[Conv {conversation_id}] Placeholder assistant message created (ID: {assistant_message.id})")

    # Trigger Celery task
    task = process_openai_stream.apply_async(
        args=[assistant_message.id, message.content, conversation_id]
    )
    
    logger.info(f"[Conv {conversation_id}] Celery task triggered: {task.id}")
    logger.info(f"[Conv {conversation_id}] Client should stream from: /stream/{task.id}")
    
    return {
        "task_id": task.id,
        "message_id": assistant_message.id,
        "status": "processing"
    }


@app.get("/stream/{task_id}")
async def stream_response(
    task_id: str,
    session: Session = Depends(get_session)
):
    """
    Stream the AI response from the database as chunks become available.
    This endpoint polls the database and streams chunks to the client.
    """
    logger.info(f"[Stream {task_id}] Client connected for streaming")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Stream chunks from database as they become available"""
        last_chunk_index = -1
        done = False
        max_wait_time = 300  # 5 minutes timeout
        start_time = datetime.now()
        
        while not done:
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait_time:
                logger.warning(f"[Stream {task_id}] Timeout reached after {elapsed:.1f}s")
                yield f"data: {json.dumps({'error': 'Stream timeout'})}\n\n"
                break
            
            # Fetch new chunks
            statement = select(StreamChunk).where(
                StreamChunk.task_id == task_id,
                StreamChunk.chunk_index > last_chunk_index
            ).order_by(StreamChunk.chunk_index)
            
            chunks = session.exec(statement).all()
            
            if chunks:
                for chunk in chunks:
                    last_chunk_index = chunk.chunk_index
                    
                    if chunk.chunk_type == "content":
                        yield f"data: {json.dumps({'content': chunk.content})}\n\n"
                    elif chunk.chunk_type == "reasoning":
                        yield f"data: {json.dumps({'reasoning': chunk.content})}\n\n"
                    elif chunk.chunk_type == "done":
                        logger.info(f"[Stream {task_id}] Stream completed")
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        done = True
                        break
                    elif chunk.chunk_type == "error":
                        logger.error(f"[Stream {task_id}] Error: {chunk.content}")
                        yield f"data: {json.dumps({'error': chunk.content})}\n\n"
                        done = True
                        break
            else:
                # No new chunks, wait a bit before polling again
                await asyncio.sleep(0.1)  # 100ms polling interval
        
        logger.info(f"[Stream {task_id}] Stream ended")
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
