# Documentation Index

This project has multiple documentation files. Here's what to read based on your needs:

## 📖 Start Here

**New to this project?** Start with these:

1. **[README.md](README.md)** - Main project documentation
   - Architecture overview
   - Setup instructions
   - API endpoints
   - Technology stack

2. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
   - Quick setup guide
   - Common troubleshooting

## 🎯 Core Documentation (Current Implementation)

**Read these to understand how the system works:**

- **[WHY_REDIS.md](WHY_REDIS.md)** - Why Redis pub/sub for streaming?
  - Comparison: Database polling vs Redis pub/sub
  - Performance metrics (30x faster!)
  - Clear explanations with analogies

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment guide
  - How the system works
  - Monitoring and troubleshooting
  - Production considerations

- **[backend/ARCHITECTURE_COMPARISON.md](backend/ARCHITECTURE_COMPARISON.md)** - Technical deep-dive
  - Side-by-side code comparison
  - Performance metrics
  - Architecture decisions

## 📚 Historical/Migration Documentation

**These docs explain the evolution of the project. Read if you're curious about the history:**

- **[CHANGES.md](CHANGES.md)** - Version history and changelog
  - Documents migration from database to Redis streaming

- **[REDIS_STREAMING.md](REDIS_STREAMING.md)** - Redis streaming implementation details
  - Historical perspective on migration
  - Technical details about Redis pub/sub

- **[MIGRATION_TO_REDIS.md](MIGRATION_TO_REDIS.md)** - Migration guide
  - Historical: Documents the migration process from DB to Redis

- **[REDIS_IMPLEMENTATION_SUMMARY.md](REDIS_IMPLEMENTATION_SUMMARY.md)** - Quick reference
  - Summary of Redis implementation

- **[REDIS_QUICK_START.md](REDIS_QUICK_START.md)** - Redis-specific quick start

- **[DIRECT_REDIS_USAGE.md](DIRECT_REDIS_USAGE.md)** - Direct Redis usage patterns
  - Documents removal of redis_client.py wrapper

- **[ASYNC_REDIS_FIX.md](ASYNC_REDIS_FIX.md)** - Async Redis implementation notes
  - Historical: Documents fixing async/blocking issues

- **[BLOCKING_VS_ASYNC.md](BLOCKING_VS_ASYNC.md)** - Blocking vs async patterns
  - Educational: Explains async programming concepts

## 🎓 What Should I Read?

### I want to...

**...understand the project quickly**
→ Read: README.md, WHY_REDIS.md

**...get it running ASAP**
→ Read: QUICKSTART.md

**...deploy to production**
→ Read: DEPLOYMENT.md

**...understand why Redis was chosen**
→ Read: WHY_REDIS.md, backend/ARCHITECTURE_COMPARISON.md

**...see the full history of changes**
→ Read: CHANGES.md, migration docs

**...learn about async programming**
→ Read: BLOCKING_VS_ASYNC.md

## 🔍 Current Architecture Summary

**How it works:**
1. User sends message → FastAPI creates Celery task
2. Celery worker streams from OpenAI → publishes chunks to Redis pub/sub
3. FastAPI subscribes to Redis channel → streams to client via SSE
4. Worker saves final message to PostgreSQL
5. Redis chunks auto-expire after 1 hour

**Key technologies:**
- **FastAPI**: HTTP API and SSE streaming
- **Celery**: Background task processing
- **Redis**: Pub/sub for real-time streaming + Celery broker
- **PostgreSQL**: Persistent storage for messages
- **OpenAI API**: AI responses

**Performance:**
- <5ms streaming latency (30x faster than database polling)
- Handles 1000+ concurrent streams
- Zero polling overhead (push-based delivery)

## 📝 Documentation Maintenance

**Active docs** (keep updated):
- README.md
- WHY_REDIS.md
- DEPLOYMENT.md
- QUICKSTART.md
- backend/ARCHITECTURE_COMPARISON.md

**Historical docs** (archive, don't delete):
- CHANGES.md
- REDIS_STREAMING.md
- MIGRATION_TO_REDIS.md
- Other migration/fix docs

**Consider consolidating** in the future:
- Multiple Redis docs could be merged
- Keep WHY_REDIS.md as the main explanation

