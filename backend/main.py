from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session
from openai import AsyncOpenAI
import os
from typing import AsyncGenerator, List, Dict, Any
import json
import logging
import asyncio
from datetime import datetime
import redis.asyncio as redis

from database import engine, get_session
from models import Conversation as ConversationModel, Message as MessageModel
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

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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
    
    # Save task_id to the message immediately for reconnection support
    assistant_message.task_id = task.id
    session.add(assistant_message)
    session.commit()
    
    logger.info(f"[Conv {conversation_id}] Celery task triggered: {task.id}")
    logger.info(f"[Conv {conversation_id}] Client should stream from: /stream/{task.id}")
    
    return {
        "task_id": task.id,
        "message_id": assistant_message.id,
        "status": "processing"
    }


@app.get("/stream/{task_id}")
async def stream_response(task_id: str):
    """
    Stream the AI response from Redis using pub/sub for real-time delivery.
    This eliminates database polling and provides sub-millisecond latency.
    
    Uses redis.asyncio for proper async/await support.
    """
    logger.info(f"[Stream {task_id}] Client connected for streaming")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Stream chunks from Redis using async pub/sub (no blocking!)"""
        done = False
        max_wait_time = 300  # 5 minutes timeout
        start_time = datetime.now()
        
        # First, send any chunks that already exist (in case we're late to the party)
        # Get existing chunks from Redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        try:
            list_key = f"stream:{task_id}:chunks"
            chunk_strings = await r.lrange(list_key, 0, -1)
            existing_chunks = [json.loads(chunk_str) for chunk_str in chunk_strings]
        finally:
            await r.aclose()
        
        for chunk_data in existing_chunks:
            chunk_type = chunk_data.get("chunk_type")
            content = chunk_data.get("content", "")
            
            if chunk_type == "content":
                yield f"data: {json.dumps({'content': content})}\n\n"
            elif chunk_type == "reasoning":
                yield f"data: {json.dumps({'reasoning': content})}\n\n"
            elif chunk_type == "done":
                logger.info(f"[Stream {task_id}] Stream already completed")
                yield f"data: {json.dumps({'done': True})}\n\n"
                done = True
                return
            elif chunk_type == "error":
                logger.error(f"[Stream {task_id}] Error: {content}")
                yield f"data: {json.dumps({'error': content})}\n\n"
                done = True
                return
        
        # If already done, don't subscribe
        if done:
            return
        
        # Subscribe to Redis pub/sub for real-time chunks using async context manager
        r = redis.from_url(REDIS_URL, decode_responses=True)
        
        try:
            async with r.pubsub() as pubsub:
                channel = f"stream:{task_id}"
                await pubsub.subscribe(channel)
                
                logger.info(f"[Stream {task_id}] Subscribed to Redis pub/sub channel")
                
                # Process messages from pub/sub using async get_message
                # This is non-blocking and allows multiple concurrent streams
                while not done:
                    # Check timeout
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed > max_wait_time:
                        logger.warning(f"[Stream {task_id}] Timeout reached after {elapsed:.1f}s")
                        yield f"data: {json.dumps({'error': 'Stream timeout'})}\n\n"
                        break
                    
                    # Get message with timeout (async, non-blocking)
                    # timeout=1.0 means wait up to 1 second for a message
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    
                    if message is None:
                        # No message yet, continue waiting
                        # The timeout in get_message handles the waiting, so we don't block
                        continue
                    
                    # Process the message
                    if message['type'] == 'message':
                        try:
                            chunk_data = json.loads(message['data'])
                            chunk_type = chunk_data.get("chunk_type")
                            content = chunk_data.get("content", "")
                            
                            if chunk_type == "content":
                                yield f"data: {json.dumps({'content': content})}\n\n"
                            elif chunk_type == "reasoning":
                                yield f"data: {json.dumps({'reasoning': content})}\n\n"
                            elif chunk_type == "done":
                                logger.info(f"[Stream {task_id}] Stream completed")
                                yield f"data: {json.dumps({'done': True})}\n\n"
                                done = True
                                break
                            elif chunk_type == "error":
                                logger.error(f"[Stream {task_id}] Error: {content}")
                                yield f"data: {json.dumps({'error': content})}\n\n"
                                done = True
                                break
                        except json.JSONDecodeError:
                            logger.error(f"[Stream {task_id}] Failed to decode message")
                            continue
                
                logger.info(f"[Stream {task_id}] Stream ended")
        
        finally:
            # Cleanup Redis client
            await r.aclose()
    
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
