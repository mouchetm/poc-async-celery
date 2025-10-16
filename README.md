# Chat Application with FastAPI and Next.js

A full-stack chat application with streaming AI responses powered by OpenAI, built with FastAPI (backend), Next.js (frontend), and PostgreSQL (database).

## Project Structure

```
.
├── backend/              # FastAPI backend
│   ├── main.py          # Main FastAPI application
│   ├── database.py      # Database configuration
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   ├── requirements.txt # Python dependencies
│   └── .env.example     # Environment variables example
├── test-clients/        # Test clients for the API
│   ├── test_sync.py     # Synchronous test client
│   ├── test_async.py    # Asynchronous test client
│   ├── test_load.py     # Load testing client
│   └── requirements.txt # Python dependencies
└── frontend/            # Next.js frontend
    ├── app/             # Next.js app directory
    ├── package.json     # Node dependencies
    └── .env.example     # Environment variables example
```

## Features

- **Create conversations**: Start new chat conversations
- **Stream AI responses**: Real-time streaming of AI-generated responses using OpenAI
- **Persistent storage**: All conversations and messages stored in PostgreSQL
- **Modern UI**: Clean, responsive chat interface built with Next.js and Tailwind CSS
- **Testing tools**: Sync, async, and load testing clients included

## Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher
- PostgreSQL database
- OpenAI API key

## Setup Instructions

### 1. Database Setup

Install and start PostgreSQL, then create a database:

```bash
# Using PostgreSQL command line
createdb chatdb

# Or using psql
psql -U postgres
CREATE DATABASE chatdb;
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=your_openai_api_key_here
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatdb
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create .env.local file
cp .env.example .env.local

# The default API URL is http://localhost:8000
# Modify if needed in .env.local
```

### 4. Test Clients Setup (Optional)

```bash
# Navigate to test-clients directory
cd test-clients

# Create a virtual environment (if not using backend's venv)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

### Start the Backend

```bash
cd backend
source venv/bin/activate  # Activate venv if not already active
python main.py
```

The backend API will be available at `http://localhost:8000`

You can visit `http://localhost:8000/docs` to see the interactive API documentation.

### Start the Frontend

In a new terminal:

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Using the Application

1. Open your browser and navigate to `http://localhost:3000`
2. Click "Start New Conversation" or "New Conversation" button
3. Type your message in the input field
4. Press "Send" or hit Enter
5. Watch the AI response stream in real-time
6. Continue the conversation or start a new one

## Testing the API

### Synchronous Test

Test basic request/response:

```bash
cd test-clients
python test_sync.py
```

### Asynchronous Test

Test async functionality:

```bash
cd test-clients
python test_async.py
```

### Load Testing

Simulate multiple concurrent users (default: 10 users):

```bash
cd test-clients
python test_load.py

# Or specify number of users:
python test_load.py --users 50
```

## API Endpoints

### Create Conversation
- **POST** `/conversations`
- Body: `{"title": "Conversation Title"}`
- Returns: Conversation object with ID

### Get Conversation
- **GET** `/conversations/{conversation_id}`
- Returns: Conversation object with all messages

### Send Message
- **POST** `/conversations/{conversation_id}/messages`
- Body: `{"content": "Your message"}`
- Returns: Server-Sent Events (SSE) stream with AI response

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Relational database
- **OpenAI API**: AI-powered chat responses
- **Uvicorn**: ASGI server

### Frontend
- **Next.js 14**: React framework with App Router
- **React**: UI library
- **AI SDK**: Vercel's AI SDK for streaming responses
- **Tailwind CSS**: Utility-first CSS framework
- **TypeScript**: Type-safe JavaScript

### Test Clients
- **requests**: HTTP library for Python (sync)
- **aiohttp**: Async HTTP client for Python
- **asyncio**: Async I/O framework

## Environment Variables

### Backend (.env)
```
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatdb
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Check database credentials in `DATABASE_URL`
- Verify the database `chatdb` exists

### OpenAI API Errors
- Verify your OpenAI API key is valid
- Check you have sufficient API credits
- Ensure the API key is properly set in backend/.env

### CORS Issues
- The backend is configured to allow all origins in development
- For production, update CORS settings in `backend/main.py`

### Frontend Connection Issues
- Ensure backend is running on port 8000
- Check `NEXT_PUBLIC_API_URL` in frontend/.env.local
- Verify there are no firewall blocking localhost connections

## Development Notes

- The backend automatically creates database tables on startup
- Messages are streamed using Server-Sent Events (SSE)
- The frontend uses the AI SDK's `useChat` hook for handling streaming
- All conversations and messages are persisted to the database

## Production Deployment

For production deployment, consider:

1. Set proper CORS origins in backend
2. Use environment-specific database credentials
3. Enable HTTPS for both frontend and backend
4. Set up proper error logging and monitoring
5. Configure rate limiting for the API
6. Use a production-ready database (managed PostgreSQL)
7. Deploy frontend to Vercel or similar platform
8. Deploy backend to a cloud provider with proper scaling

## License

MIT
# poc-async-celery
