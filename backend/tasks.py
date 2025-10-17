from celery_config import celery_app
from openai import AsyncOpenAI
from sqlmodel import Session
from models import Message as MessageModel
from database import engine
import os
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any
import redis.asyncio as redis

# Configure logging
logger = logging.getLogger("celery_tasks")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHUNK_TTL = 3600  # 1 hour TTL for chunks


@celery_app.task(bind=True)
def process_openai_stream(self, message_id: int, user_content: str, conversation_id: int):
    """
    Celery task that processes OpenAI stream and stores chunks in database.
    This runs independently of the HTTP connection, so if the user disconnects,
    the task continues running.
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting OpenAI stream processing for message {message_id}")
    
    # Run the async function in the event loop
    asyncio.run(process_stream_async(task_id, message_id, user_content, conversation_id))
    
    return {"status": "completed", "message_id": message_id}


async def store_chunk(task_id: str, chunk_data: Dict[str, Any]) -> None:
    """Store a chunk in Redis and publish to pub/sub channel."""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        list_key = f"stream:{task_id}:chunks"
        chunk_json = json.dumps(chunk_data)
        
        # Push chunk to list
        await r.rpush(list_key, chunk_json)
        
        # Set TTL on the list (resets with each chunk)
        await r.expire(list_key, CHUNK_TTL)
        
        # Publish notification that a new chunk is available
        channel = f"stream:{task_id}"
        await r.publish(channel, chunk_json)
    finally:
        await r.aclose()


async def store_stream_metadata(task_id: str, metadata: Dict[str, Any]) -> None:
    """Store metadata about a stream."""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        metadata_key = f"stream:{task_id}:metadata"
        await r.hset(metadata_key, mapping={k: json.dumps(v) for k, v in metadata.items()})
        await r.expire(metadata_key, CHUNK_TTL)
    finally:
        await r.aclose()


async def process_stream_async(task_id: str, message_id: int, user_content: str, conversation_id: int):
    """Async function that handles the OpenAI stream"""
    stream_start = datetime.now()
    assistant_content = ""
    assistant_reasoning = ""
    chunk_count = 0
    chunk_index = 0
    
    # Store metadata in Redis
    await store_stream_metadata(task_id, {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "status": "processing",
        "started_at": stream_start.isoformat()
    })
    
    try:
        logger.info(f"[Task {task_id}] Starting OpenAI stream request...")
        
        # Create streaming response from OpenAI
        stream = await openai_client.responses.create(
            model="gpt-5",
            input=user_content,
            reasoning={"effort": "high", "summary": "auto"},
            stream=True
        )
        
        first_chunk_time = None
        logger.info(f"[Task {task_id}] Stream connection established, waiting for first chunk...")
        
        # Handle each streamed event as it arrives
        async for event in stream:
            if not hasattr(event, "type"):
                continue
            
            # Handle response text deltas
            if event.type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    if first_chunk_time is None:
                        first_chunk_time = datetime.now()
                        ttfb = (first_chunk_time - stream_start).total_seconds()
                        logger.info(f"[Task {task_id}] First chunk received! TTFB: {ttfb:.3f}s")
                    
                    chunk_count += 1
                    assistant_content += delta
                    
                    # Store chunk in Redis
                    await store_chunk(task_id, {
                        "chunk_index": chunk_index,
                        "chunk_type": "content",
                        "content": delta
                    })
                    chunk_index += 1
                    
                    if chunk_count % 10 == 0:
                        elapsed = (datetime.now() - stream_start).total_seconds()
                        logger.info(f"[Task {task_id}] Progress: chunks={chunk_count}, "
                                  f"chars={len(assistant_content)}, elapsed={elapsed:.2f}s")
            
            # Handle reasoning
            elif event.type == "response.reasoning_summary_text.delta":
                reasoning_delta = getattr(event, "delta", "")
                if reasoning_delta:
                    assistant_reasoning += reasoning_delta
                    
                    # Store reasoning chunk in Redis
                    await store_chunk(task_id, {
                        "chunk_index": chunk_index,
                        "chunk_type": "reasoning",
                        "content": reasoning_delta
                    })
                    chunk_index += 1
                    
                    logger.info(f"[Task {task_id}] Reasoning chunk received")
        
        # Update the message with final content in database
        with Session(engine) as session:
            message = session.get(MessageModel, message_id)
            if message:
                message.content = assistant_content
                message.reasoning = assistant_reasoning if assistant_reasoning else None
                message.task_id = task_id
                session.add(message)
                session.commit()
                logger.info(f"[Task {task_id}] Message updated with final content")
        
        # Store done marker in Redis
        await store_chunk(task_id, {
            "chunk_index": chunk_index,
            "chunk_type": "done",
            "content": ""
        })
        
        # Update metadata
        await store_stream_metadata(task_id, {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "chunk_count": chunk_count,
            "content_length": len(assistant_content)
        })
        
        stream_end = datetime.now()
        total_time = (stream_end - stream_start).total_seconds()
        
        logger.info(f"[Task {task_id}] Stream completed!")
        logger.info(f"[Task {task_id}] Stats: chunks={chunk_count}, chars={len(assistant_content)}, time={total_time:.3f}s")
        
    except Exception as e:
        logger.error(f"[Task {task_id}] ERROR: {str(e)}")
        
        # Store error chunk in Redis
        await store_chunk(task_id, {
            "chunk_index": chunk_index,
            "chunk_type": "error",
            "content": str(e)
        })
        
        # Update metadata
        await store_stream_metadata(task_id, {
            "status": "error",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })
        
        raise

