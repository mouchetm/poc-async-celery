"""
Test script to verify Redis streaming functionality.
Run this after starting Redis, PostgreSQL, Celery worker, and FastAPI server.

Usage:
    python test_redis_streaming.py
"""

import requests
import json
import time
import sys

API_URL = "http://localhost:8000"


def test_redis_streaming():
    """Test the Redis-based streaming implementation"""
    
    print("=" * 80)
    print("REDIS STREAMING TEST")
    print("=" * 80)
    print()
    
    # 1. Create conversation
    print("1. Creating conversation...")
    response = requests.post(
        f"{API_URL}/conversations",
        json={"title": "Redis Streaming Test"}
    )
    if response.status_code != 200:
        print(f"❌ Failed to create conversation: {response.text}")
        return
    
    conversation = response.json()
    conversation_id = conversation["id"]
    print(f"✓ Conversation created: ID={conversation_id}")
    print()
    
    # 2. Send message
    print("2. Sending message...")
    message_text = "Explain quantum computing in simple terms. Make it about 200 words."
    response = requests.post(
        f"{API_URL}/conversations/{conversation_id}/messages",
        json={"content": message_text}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to send message: {response.text}")
        return
    
    result = response.json()
    task_id = result["task_id"]
    message_id = result["message_id"]
    
    print(f"✓ Message sent!")
    print(f"  Task ID: {task_id}")
    print(f"  Message ID: {message_id}")
    print()
    
    # 3. Stream response
    print("3. Streaming response from Redis pub/sub...")
    print("-" * 80)
    
    stream_start = time.time()
    first_chunk_time = None
    chunk_count = 0
    total_content = ""
    
    try:
        with requests.get(
            f"{API_URL}/stream/{task_id}",
            stream=True,
            timeout=120
        ) as response:
            
            if response.status_code != 200:
                print(f"❌ Stream failed: {response.text}")
                return
            
            print("📡 Connected to stream (Redis pub/sub)...\n")
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                line = line.decode('utf-8')
                
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove 'data: ' prefix
                    
                    try:
                        data = json.loads(data_str)
                        
                        if 'content' in data:
                            if first_chunk_time is None:
                                first_chunk_time = time.time()
                                ttfb = (first_chunk_time - stream_start) * 1000
                                print(f"⚡ First chunk received! TTFB: {ttfb:.1f}ms")
                                print()
                            
                            chunk_count += 1
                            content = data['content']
                            total_content += content
                            
                            # Print content
                            print(content, end='', flush=True)
                        
                        elif 'reasoning' in data:
                            reasoning = data['reasoning']
                            print(f"\n\n🧠 Reasoning: {reasoning}")
                        
                        elif data.get('done'):
                            stream_end = time.time()
                            total_time = (stream_end - stream_start) * 1000
                            
                            print("\n")
                            print("-" * 80)
                            print("✓ Stream completed!")
                            print()
                            print("📊 Statistics:")
                            print(f"  - Total chunks: {chunk_count}")
                            print(f"  - Total characters: {len(total_content)}")
                            print(f"  - Time to first byte: {ttfb:.1f}ms")
                            print(f"  - Total time: {total_time:.1f}ms")
                            print(f"  - Average latency: {total_time/chunk_count:.1f}ms per chunk")
                            print()
                            break
                        
                        elif 'error' in data:
                            print(f"\n❌ Error: {data['error']}")
                            break
                    
                    except json.JSONDecodeError:
                        continue
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print()
    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


def test_redis_connection():
    """Test Redis connectivity"""
    try:
        import redis
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        r.close()
        print("✓ Redis is connected and working")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("\nMake sure Redis is running:")
        print("  redis-server")
        return False


def test_api_connection():
    """Test API connectivity"""
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code == 200:
            print("✓ FastAPI server is running")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to FastAPI server")
        print("\nMake sure the server is running:")
        print("  cd backend")
        print("  uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False


if __name__ == "__main__":
    print()
    print("Checking prerequisites...")
    print()
    
    redis_ok = test_redis_connection()
    api_ok = test_api_connection()
    
    print()
    
    if not redis_ok or not api_ok:
        print("⚠️ Prerequisites not met. Please fix the above issues.")
        sys.exit(1)
    
    print("All prerequisites met! Starting test...")
    print()
    time.sleep(1)
    
    test_redis_streaming()

