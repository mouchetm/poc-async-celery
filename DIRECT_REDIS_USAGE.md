# Direct Redis Usage - Removed redis_client Module

> 📘 **Current Implementation**: This documents the current Redis usage patterns.
> The code uses `redis.asyncio` directly (no wrapper module).

## Overview

Removed the `redis_client.py` wrapper module and now use `redis.asyncio` directly in the codebase. This simplifies the architecture and follows the official Redis asyncio documentation more closely.

## Changes Made

### 1. Removed Files
- ❌ `backend/redis_client.py` - Wrapper module (deleted)
- ❌ `backend/test_async_redis.py` - Test for the wrapper (deleted)
- ❌ `ASYNC_REDIS_UPDATE.md` - Documentation about the wrapper (deleted)

### 2. Updated `backend/main.py`

**Changes:**
- Removed: `from redis_client import get_chunks, get_redis_client`
- Added: `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")`
- Updated `stream_response()` endpoint to use `redis.from_url()` directly
- Inlined the chunk retrieval logic (previously `get_chunks()` function)

**Key Pattern:**
```python
# Get existing chunks
r = redis.from_url(REDIS_URL, decode_responses=True)
try:
    list_key = f"stream:{task_id}:chunks"
    chunk_strings = await r.lrange(list_key, 0, -1)
    existing_chunks = [json.loads(chunk_str) for chunk_str in chunk_strings]
finally:
    await r.aclose()

# Subscribe to pub/sub
r = redis.from_url(REDIS_URL, decode_responses=True)
try:
    async with r.pubsub() as pubsub:
        await pubsub.subscribe(f"stream:{task_id}")
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        # Process messages...
finally:
    await r.aclose()
```

### 3. Updated `backend/tasks.py`

**Changes:**
- Removed: `from redis_client import store_chunk, store_stream_metadata`
- Added: `import redis.asyncio as redis`
- Added: `REDIS_URL` and `CHUNK_TTL` constants
- Inlined `store_chunk()` and `store_stream_metadata()` as local async functions

**Key Pattern:**
```python
async def store_chunk(task_id: str, chunk_data: Dict[str, Any]) -> None:
    """Store a chunk in Redis and publish to pub/sub channel."""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        list_key = f"stream:{task_id}:chunks"
        chunk_json = json.dumps(chunk_data)
        
        # Push chunk to list
        await r.rpush(list_key, chunk_json)
        
        # Set TTL
        await r.expire(list_key, CHUNK_TTL)
        
        # Publish to pub/sub
        channel = f"stream:{task_id}"
        await r.publish(channel, chunk_json)
    finally:
        await r.aclose()
```

### 4. Updated `backend/test_redis_streaming.py`

**Changes:**
- Updated `test_redis_connection()` to use `redis.from_url()` directly instead of importing from `redis_client`
- Uses synchronous `redis` (not `redis.asyncio`) since it's a simple connection test

## Benefits

1. **Simpler Architecture**: No intermediate wrapper module
2. **Direct Control**: Direct access to Redis operations
3. **Less Abstraction**: Easier to understand what's happening
4. **Official Pattern**: Follows redis-py documentation exactly
5. **Easier Maintenance**: Fewer files to maintain

## Redis Operations

All Redis operations now use this pattern:

```python
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create client
r = redis.from_url(REDIS_URL, decode_responses=True)

try:
    # Use client
    await r.set("key", "value")
    value = await r.get("key")
    
    # Pub/Sub
    async with r.pubsub() as pubsub:
        await pubsub.subscribe("channel")
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
finally:
    # Always close
    await r.aclose()
```

## Configuration

Redis URL is configured via environment variable:
```bash
REDIS_URL=redis://localhost:6379/0
```

Falls back to `redis://localhost:6379/0` if not set.

## Testing

Run the test script to verify everything works:
```bash
cd backend
source venv/bin/activate
python test_redis_streaming.py
```

## Migration from Previous Version

If you had code importing from `redis_client`:

**Before:**
```python
from redis_client import get_redis_client, store_chunk, get_chunks

client = get_redis_client()
await store_chunk(task_id, chunk_data)
chunks = await get_chunks(task_id)
```

**After:**
```python
import redis.asyncio as redis
import json

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Get chunks
r = redis.from_url(REDIS_URL, decode_responses=True)
try:
    chunk_strings = await r.lrange(f"stream:{task_id}:chunks", 0, -1)
    chunks = [json.loads(s) for s in chunk_strings]
finally:
    await r.aclose()

# Store chunk
r = redis.from_url(REDIS_URL, decode_responses=True)
try:
    await r.rpush(f"stream:{task_id}:chunks", json.dumps(chunk_data))
    await r.expire(f"stream:{task_id}:chunks", 3600)
    await r.publish(f"stream:{task_id}", json.dumps(chunk_data))
finally:
    await r.aclose()
```

## References

- Redis-py async documentation: https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
- Pub/Sub examples: See "Pub/Sub Mode" section in the documentation

