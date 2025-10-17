# Stream Reconnection & Multi-Browser Support

## Overview

The frontend now automatically reconnects to ongoing streams when you refresh the page or open the conversation in multiple browsers.

## How It Works

### 1. **Refresh During Streaming**

When you refresh the browser while a message is streaming:

1. **Frontend loads conversation** from database
2. **Detects incomplete message**: Last assistant message has `task_id` but no content
3. **Automatically reconnects** to the Redis stream using the `task_id`
4. **Receives all chunks**: Backend sends all chunks from Redis (both existing and new)
5. **Stream continues**: You see the response build up from the beginning

**Result**: You don't lose progress! The stream reconnects and displays the full response.

### 2. **Multiple Browsers**

When you open the same conversation in multiple browsers during streaming:

**Each browser independently:**
1. Loads the conversation from database
2. Detects incomplete message (empty content + task_id)
3. Subscribes to the same Redis pub/sub channel
4. Receives chunks in real-time

**Result**: All browsers receive the same chunks simultaneously via Redis pub/sub! ✨

### Technical Details

#### Backend (Redis Pub/Sub)
- **Redis pub/sub supports multiple subscribers** - no limit on concurrent browsers
- When Celery worker publishes a chunk, **all subscribed clients receive it instantly**
- Each client maintains independent SSE connection to FastAPI
- Redis doesn't care how many clients are listening

#### Frontend Detection
```typescript
// Detect incomplete stream on page load
const lastMessage = loadedMessages[loadedMessages.length - 1];
if (
  lastMessage &&
  lastMessage.role === 'assistant' &&
  lastMessage.task_id &&
  !lastMessage.content  // Empty = incomplete
) {
  // Reconnect!
  await resumeStream(lastMessage.task_id, lastMessage.id);
}
```

#### Stream Resumption
```typescript
// Backend sends ALL chunks from Redis first
1. GET /stream/{task_id}
2. Backend fetches: redis.lrange(f"stream:{task_id}:chunks", 0, -1)
3. Sends all existing chunks via SSE
4. Subscribes to pub/sub for new chunks
5. Continues streaming until 'done'
```

## Example Scenarios

### Scenario 1: Refresh During Stream

```
Timeline:
t=0s   - User sends message "Explain quantum physics"
t=1s   - Stream starts, receiving chunks...
t=3s   - User refreshes browser 🔄
t=3.1s - Frontend detects incomplete message
t=3.2s - Reconnects to stream
t=3.3s - Receives all chunks (0-100) from Redis
t=4s   - Continues receiving new chunks (101, 102, 103...)
t=10s  - Stream completes, 'done' received
```

**User Experience**: Seamless! Response appears to continue streaming from the beginning.

### Scenario 2: Open in Multiple Browsers

```
Browser 1:
t=0s   - Sends message
t=1s   - Streaming... (chunks 1-50)

Browser 2:
t=2s   - Opens same conversation
t=2.1s - Detects incomplete stream
t=2.2s - Reconnects
t=2.3s - Receives chunks 1-50 from Redis (catch up)
t=3s   - Receives chunk 51 (real-time)
t=3.1s - Receives chunk 52 (real-time)

Both browsers now streaming in sync! 🎉
```

**User Experience**: Both browsers show the same response building up in real-time.

## Edge Cases

### Case 1: Stream Already Completed
If you try to reconnect to a completed stream:
- Backend finds 'done' chunk in Redis
- Sends all chunks + 'done' immediately
- Connection closes
- **Result**: You see the full response instantly

### Case 2: Redis Chunks Expired (>1 hour)
If chunks have expired from Redis:
- Backend finds no chunks
- Subscribes to pub/sub (but stream is dead)
- Timeout after 5 minutes
- **Result**: Empty response (but final message is in PostgreSQL)

### Case 3: Stream Failed
If the Celery task failed:
- Redis has an 'error' chunk
- Backend sends error to frontend
- **Result**: Error message displayed

## Benefits

✅ **Resilient**: Refresh doesn't lose your response  
✅ **Multi-device**: Check progress on phone while streaming on desktop  
✅ **Collaborative**: Multiple users can watch the same response being generated  
✅ **Scalable**: Redis pub/sub handles thousands of concurrent subscribers  
✅ **No Duplication**: Frontend resets content when reconnecting to avoid duplicates  

## Implementation Notes

### Frontend Changes
- Added `task_id` to Message interface
- Added `streamFromTask()` function with `isResume` parameter
- Added `resumeStream()` function for reconnection
- Detection logic in `loadConversation()`
- Content reset on resume to avoid duplication

### Backend (No Changes Needed!)
- Already supports multiple concurrent subscribers
- Already sends existing chunks first
- Already handles pub/sub correctly
- TTL of 1 hour for chunks

## Testing

### Test Refresh:
1. Start a conversation
2. Send a message
3. While streaming, refresh the page
4. ✅ Stream should reconnect and continue

### Test Multiple Browsers:
1. Start a conversation in Browser 1
2. Send a message
3. While streaming, open same conversation in Browser 2
4. ✅ Both should show streaming in real-time

### Test Completed Stream:
1. Send a message and wait for completion
2. Refresh the page
3. ✅ Should show completed message (not reconnect)

## Limitations

1. **1-hour TTL**: Chunks expire after 1 hour. If you try to reconnect after that, you won't see the stream.
2. **Final Message**: If chunks expired, the completed message is still in PostgreSQL.
3. **Bandwidth**: Each browser uses bandwidth to receive all chunks independently.
4. **No Pause/Resume**: Can't pause a stream and resume later (would need additional state management).

## Future Enhancements

- **WebSocket support**: Replace SSE with WebSockets for bidirectional communication
- **Chunk compression**: Reduce bandwidth usage
- **Selective resume**: Resume from last received chunk (would need client-side tracking)
- **Stream pagination**: For very long responses

