"""
Load test client for the Chat API
Simulates multiple concurrent users making requests
"""
import asyncio
import aiohttp
import json
import time
from typing import List
import argparse


API_BASE_URL = "http://localhost:8000"


async def simulate_user(session: aiohttp.ClientSession, user_id: int):
    """Simulate a single user's interaction with the API"""

    try:
        # Create a conversation
        async with session.post(
            f"{API_BASE_URL}/conversations",
            json={"title": f"Load Test User {user_id}"}
        ) as response:
            if response.status != 200:
                print(f"User {user_id}: Failed to create conversation")
                return False
            conversation = await response.json()
            conversation_id = conversation["id"]

        # Send a message
        message_content = f"Tell me a short fact about number {user_id}"
        start_time = time.time()

        async with session.post(
            f"{API_BASE_URL}/conversations/{conversation_id}/messages",
            json={"content": message_content}
        ) as response:
            if response.status != 200:
                print(f"User {user_id}: Failed to send message")
                return False

            # Consume the stream
            full_response = ""
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'content' in data:
                        full_response += data['content']

        end_time = time.time()
        duration = end_time - start_time

        print(f"User {user_id}: Completed in {duration:.2f}s (response length: {len(full_response)} chars)")
        return True

    except Exception as e:
        print(f"User {user_id}: Error - {str(e)}")
        return False


async def run_load_test(num_users: int):
    """Run load test with specified number of concurrent users"""

    print(f"Starting load test with {num_users} concurrent users...")
    print("-" * 60)

    start_time = time.time()

    # Create a session with connection pooling
    connector = aiohttp.TCPConnector(limit=num_users)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Run all users concurrently
        tasks = [simulate_user(session, i) for i in range(1, num_users + 1)]
        results = await asyncio.gather(*tasks)

    end_time = time.time()
    total_duration = end_time - start_time

    # Print summary
    print("-" * 60)
    print(f"\nLoad Test Summary:")
    print(f"Total users: {num_users}")
    print(f"Successful: {sum(results)}")
    print(f"Failed: {num_users - sum(results)}")
    print(f"Total duration: {total_duration:.2f}s")
    print(f"Average time per user: {total_duration / num_users:.2f}s")

    if sum(results) > 0:
        print(f"Throughput: {sum(results) / total_duration:.2f} requests/second")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load test the Chat API")
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Number of concurrent users to simulate (default: 10)"
    )

    args = parser.parse_args()

    asyncio.run(run_load_test(args.users))
