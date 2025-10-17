# Quick Start Guide

## Prerequisites Check

```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT version();"

# Check Redis is running
redis-cli ping  # Should return "PONG"

# Check Python version
python3 --version  # Should be 3.9+

# Check Node version
node --version  # Should be 18+
```

## Installation (5 minutes)

### 1. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatdb
REDIS_URL=redis://localhost:6379/0
EOF

# Edit .env and add your OpenAI API key
nano .env
```

### 2. Frontend Setup
```bash
cd ../frontend

# Install dependencies
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

## Running (3 terminals)

### Terminal 1: Celery Worker
```bash
cd backend
source venv/bin/activate
./run_celery.sh
```

**Expected output:**
```
celery@hostname ready.
[tasks]
  . process_openai_stream
```

### Terminal 2: FastAPI Server
```bash
cd backend
source venv/bin/activate
python main.py
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
Database tables created successfully
```

### Terminal 3: Frontend
```bash
cd frontend
npm run dev
```

**Expected output:**
```
Local:   http://localhost:3000
```

## Testing the Application

1. **Open Browser**: Navigate to http://localhost:3000
2. **Create Conversation**: Click "Start New Conversation"
3. **Send Message**: Type "Hello!" and press Send
4. **Watch Streaming**: Response streams in real-time
5. **Test Resilience**: 
   - Send another message
   - Close browser immediately
   - Check Celery worker logs - task continues!
   - Reopen browser - response is saved!

## Verify Everything Works

### Check Celery is Processing
```bash
# In the Celery terminal, you should see:
[Task process_openai_stream] Starting OpenAI stream request...
```

### Check Redis
```bash
redis-cli ping  # Should return PONG
redis-cli PUBSUB CHANNELS "stream:*"  # List active streams
```

### Check API
```bash
curl http://localhost:8000/
# Should return: {"message":"Chat API is running"}
```

## Common Issues

### "ModuleNotFoundError: No module named 'celery'"
**Solution**: Activate virtual environment
```bash
cd backend
source venv/bin/activate
```

### "Connection refused" to Redis
**Solution**: Start Redis
```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

### Celery not picking up tasks
**Solution**: 
1. Check Redis is running: `redis-cli ping`
2. Restart Celery worker: `Ctrl+C` then `./run_celery.sh`

### Frontend can't connect to API
**Solution**: Verify backend is running on port 8000
```bash
curl http://localhost:8000/
```

## Next Steps

- Read `DEPLOYMENT.md` for production deployment
- Read `CHANGES.md` for architecture details
- Check `README.md` for full documentation

## Cleanup

To stop all services:
1. Frontend: `Ctrl+C` in Terminal 3
2. FastAPI: `Ctrl+C` in Terminal 2
3. Celery: `Ctrl+C` in Terminal 1
4. Redis: `brew services stop redis` (macOS) or `sudo systemctl stop redis` (Linux)

## Success Criteria ✅

You know it's working when:
- ✅ Celery shows "ready" with tasks listed
- ✅ FastAPI shows "Uvicorn running"
- ✅ Frontend loads at localhost:3000
- ✅ Messages stream in real-time
- ✅ Closing browser doesn't stop AI computation
- ✅ Reopening browser shows completed responses

Enjoy your resilient chat application! 🚀

