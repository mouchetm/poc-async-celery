from celery_config import celery_app
from openai import AsyncOpenAI
from sqlmodel import Session, select
from models import Message as MessageModel, StreamChunk
from database import engine
import os
import asyncio
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger("celery_tasks")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


async def process_stream_async(task_id: str, message_id: int, user_content: str, conversation_id: int):
    """Async function that handles the OpenAI stream"""
    stream_start = datetime.now()
    assistant_content = ""
    assistant_reasoning = ""
    chunk_count = 0
    chunk_index = 0
    
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
                    
                    # Store chunk in database
                    with Session(engine) as session:
                        chunk = StreamChunk(
                            task_id=task_id,
                            message_id=message_id,
                            chunk_index=chunk_index,
                            chunk_type="content",
                            content=delta
                        )
                        session.add(chunk)
                        session.commit()
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
                    
                    # Store reasoning chunk
                    with Session(engine) as session:
                        chunk = StreamChunk(
                            task_id=task_id,
                            message_id=message_id,
                            chunk_index=chunk_index,
                            chunk_type="reasoning",
                            content=reasoning_delta
                        )
                        session.add(chunk)
                        session.commit()
                        chunk_index += 1
                    
                    logger.info(f"[Task {task_id}] Reasoning chunk received")
        
        # Update the message with final content
        with Session(engine) as session:
            message = session.get(MessageModel, message_id)
            if message:
                message.content = assistant_content
                message.reasoning = assistant_reasoning if assistant_reasoning else None
                message.task_id = task_id
                session.add(message)
                session.commit()
                logger.info(f"[Task {task_id}] Message updated with final content")
            
            # Store done marker
            done_chunk = StreamChunk(
                task_id=task_id,
                message_id=message_id,
                chunk_index=chunk_index,
                chunk_type="done",
                content=""
            )
            session.add(done_chunk)
            session.commit()
        
        stream_end = datetime.now()
        total_time = (stream_end - stream_start).total_seconds()
        
        logger.info(f"[Task {task_id}] Stream completed!")
        logger.info(f"[Task {task_id}] Stats: chunks={chunk_count}, chars={len(assistant_content)}, time={total_time:.3f}s")
        
    except Exception as e:
        logger.error(f"[Task {task_id}] ERROR: {str(e)}")
        
        # Store error chunk
        with Session(engine) as session:
            error_chunk = StreamChunk(
                task_id=task_id,
                message_id=message_id,
                chunk_index=chunk_index,
                chunk_type="error",
                content=str(e)
            )
            session.add(error_chunk)
            session.commit()
        
        raise

