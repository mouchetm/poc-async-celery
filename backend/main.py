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
from models import Conversation as ConversationModel, Message as MessageModel
from schemas import ConversationPublic, ConversationCreate, MessageCreate
from dotenv import load_dotenv

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
    """Send a message to a conversation and stream the AI response"""
    request_start = datetime.now()
    task_id = id(asyncio.current_task())
    logger.info(f"")
    logger.info(f"{'='*80}")
    logger.info(f"📨 NEW MESSAGE REQUEST | Conversation ID: {conversation_id} | Task: {task_id}")
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
    logger.info(f"[Conv {conversation_id}] User message saved to database")

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate streaming response from OpenAI using Responses API"""
        stream_start = datetime.now()
        assistant_content = ""
        assistant_reasoning = ""
        chunk_count = 0

        try:
            logger.info(f"[Conv {conversation_id}] 🚀 Starting OpenAI stream request...")
            logger.info(f"[Conv {conversation_id}] Current time: {stream_start.strftime('%H:%M:%S.%f')[:-3]}")
            
            # Create streaming response from OpenAI using Responses API
            stream = await openai_client.responses.create(
                model="gpt-5",
                input=message.content,
                reasoning={"effort": "high", "summary": "auto"},
                stream=True
            )
            
            first_chunk_time = None
            logger.info(f"[Conv {conversation_id}] ✓ Stream connection established, waiting for first chunk...")

            # Handle each streamed event as it arrives
            async for event in stream:
                if not hasattr(event, "type"):
                    continue  # Skip malformed events

                # Handle response text deltas
                if event.type == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        if first_chunk_time is None:
                            first_chunk_time = datetime.now()
                            ttfb = (first_chunk_time - stream_start).total_seconds()
                            logger.info(f"[Conv {conversation_id}] 📦 First chunk received! TTFB: {ttfb:.3f}s")
                        
                        chunk_count += 1
                        assistant_content += delta
                        
                        # Log every 10th chunk to show progress without overwhelming logs
                        if chunk_count % 10 == 0:
                            elapsed = (datetime.now() - stream_start).total_seconds()
                            logger.info(f"[Conv {conversation_id}] Streaming... chunks: {chunk_count}, "
                                      f"chars: {len(assistant_content)}, elapsed: {elapsed:.2f}s")
                        
                        yield f"data: {json.dumps({'content': delta})}\n\n"

                # Handle reasoning progress if available
                elif event.type == "response.reasoning_summary_text.delta":
                    reasoning_delta = getattr(event, "delta", "")
                    if reasoning_delta:
                        assistant_reasoning += reasoning_delta
                        logger.info(f"[Conv {conversation_id}] 🧠 Reasoning chunk received")
                        yield f"data: {json.dumps({'reasoning': reasoning_delta})}\n\n"

                else:
                    logger.warning(f"[Conv {conversation_id}] Unknown event type: {event.type}, full event: {event}")

            # Save assistant message to database
            assistant_message = MessageModel(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_content,
                reasoning=assistant_reasoning if assistant_reasoning else None
            )
            session.add(assistant_message)
            session.commit()
            logger.info(f"[Conv {conversation_id}] Assistant message saved to database")

            # Final done signal
            stream_end = datetime.now()
            total_time = (stream_end - stream_start).total_seconds()
            request_time = (stream_end - request_start).total_seconds()
            
            logger.info(f"")
            logger.info(f"[Conv {conversation_id}] ✅ Stream completed!")
            logger.info(f"[Conv {conversation_id}] Statistics:")
            logger.info(f"[Conv {conversation_id}]   - Total chunks: {chunk_count}")
            logger.info(f"[Conv {conversation_id}]   - Total characters: {len(assistant_content)}")
            logger.info(f"[Conv {conversation_id}]   - Reasoning characters: {len(assistant_reasoning)}")
            logger.info(f"[Conv {conversation_id}]   - Stream time: {total_time:.3f}s")
            logger.info(f"[Conv {conversation_id}]   - Total request time: {request_time:.3f}s")
            logger.info(f"[Conv {conversation_id}]   - End time: {stream_end.strftime('%H:%M:%S.%f')[:-3]}")
            logger.info(f"{'='*80}")
            logger.info(f"")
            
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            error_time = datetime.now()
            logger.error(f"")
            logger.error(f"[Conv {conversation_id}] ❌ ERROR occurred!")
            logger.error(f"[Conv {conversation_id}] Error: {str(e)}")
            logger.error(f"[Conv {conversation_id}] Time: {error_time.strftime('%H:%M:%S.%f')[:-3]}")
            logger.error(f"[Conv {conversation_id}] Chunks before error: {chunk_count}")
            logger.error(f"{'='*80}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    logger.info(f"[Conv {conversation_id}] Returning StreamingResponse...")
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
